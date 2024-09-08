import copy
from typing import Any, Dict

from django.db import IntegrityError
from django.db.models import Q
from django.http import HttpRequest, JsonResponse
from django.views.defaults import page_not_found

from drf_spectacular.utils import extend_schema

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from the_wall_api.models import WallProfileProgress, WallProfile, Wall
from the_wall_api.serializers import CostOverviewSerializer, DailyIceUsageSerializer
from the_wall_api.utils import (
    MULTI_THREADED, SINGLE_THREADED, WallConstructionError,
    exposed_endpoints, generate_config_hash_details, load_wall_profiles_from_config,
    daily_ice_usage_parameters, daily_ice_usage_examples, daily_ice_usage_responses,
    cost_overview_parameters, cost_overview_examples, cost_overview_profile_id_examples,
    cost_overview_responses, num_crews_parameter
)
from the_wall_api.wall_construction import WallConstruction


class BaseWallProfileView(APIView):
    
    def initialize_wall_data(self, profile_id: int | None = None, day: int | None = None) -> Dict[str, Any]:
        """
        Initialize the wall_data dictionary to hold various control data
        throughout the wall construction simulation process.
        """
        return {
            'request_profile_id': profile_id,
            'request_day': day,
            'error_response': None,
            'multi_threaded_not_needed': None,
            'wall_construction': None,
        }

    def fetch_wall_data(
        self, wall_data: Dict[str, Any], num_crews: int, profile_id: int | None = None, request_type: str = ''
    ):
        wall_construction_config = self.get_wall_construction_config(wall_data)
        if wall_data['error_response']:
            return

        if self.is_invalid_profile_number(profile_id, wall_construction_config, wall_data):
            return

        self.set_simulation_params(wall_data, num_crews, wall_construction_config, request_type)
        
        self.get_or_create_cache(wall_data, request_type)

    def get_wall_construction_config(self, wall_data: Dict[str, Any]) -> list:
        try:
            return load_wall_profiles_from_config()
        except (WallConstructionError, FileNotFoundError) as tech_error:
            wall_data['error_response'] = self.create_technical_error_response({}, tech_error)
            return []

    def is_invalid_profile_number(self, profile_id: int | None, wall_construction_config: list, wall_data: Dict[str, Any]) -> bool:
        max_profile_number = len(wall_construction_config)
        if profile_id is not None and profile_id > max_profile_number:
            wall_data['error_response'] = self.create_out_of_range_response('profile number', max_profile_number, status.HTTP_400_BAD_REQUEST)
            return True
        return False

    def set_simulation_params(
            self, wall_data: Dict[str, Any], num_crews: int,
            wall_construction_config: list, request_type: str
    ) -> None:
        """
        Set the simulation parameters for the wall_data dictionary.
        """
        sections_count = sum(len(profile) for profile in wall_construction_config)
        wall_data['sections_count'] = sections_count

        simulation_type, wall_config_hash_details, num_crews_final = self.evaluate_simulation_params(
            num_crews, sections_count, wall_construction_config, wall_data
        )
        wall_data['num_crews'] = num_crews_final
        wall_data['wall_construction_config'] = copy.deepcopy(wall_construction_config)
        wall_data['simulation_type'] = simulation_type
        wall_data['wall_config_hash'] = wall_config_hash_details['wall_config_hash']
        wall_data['profile_config_hash_data'] = wall_config_hash_details['profile_config_hash_data']
        wall_data['request_type'] = request_type

    def evaluate_simulation_params(
            self, num_crews: int, sections_count: int, wall_construction_config: list, wall_data: Dict[str, Any]
    ) -> tuple[str, dict, int]:
        # num_crews
        if num_crews == 0:
            # No num_crews provided - single-threaded mode
            simulation_type = SINGLE_THREADED
            num_crews_final = 0
        elif num_crews >= sections_count:
            # There's a crew for each section at the beginning
            # which is the same as the single-threaded mode
            simulation_type = SINGLE_THREADED
            num_crews_final = 0
            # For eventual future response message
            wall_data['multi_threaded_not_needed'] = True
        else:
            # The crews are less than the number of sections
            simulation_type = MULTI_THREADED
            num_crews_final = num_crews

        # configuration hashes
        wall_config_hash_details = generate_config_hash_details(wall_construction_config)

        return simulation_type, wall_config_hash_details, num_crews_final
        
    def get_or_create_cache(self, wall_data, request_type) -> None:
        # Check for cached data
        self.collect_cached_data(wall_data, request_type)
        if wall_data.get('cached_result') or wall_data['error_response']:
            return
        
        # If no cached data is found, run the simulation
        self.run_simulation_and_create_cache(wall_data)

    def validate_day_within_range(self, wall_data: Dict[str, Any]) -> None:
        """
        Compare the day from the request (if provided and the max day in the simulation).
        """
        construction_days = wall_data['sim_calc_details']['construction_days']
        if wall_data['request_day'] is not None and wall_data['request_day'] > construction_days:
            wall_data['error_response'] = self.create_out_of_range_response('day', construction_days, status.HTTP_400_BAD_REQUEST)

    def collect_cached_data(self, wall_data: Dict[str, Any], request_type: str) -> None:
        """
        Checks for different type of cached data, based on the request type.
        """
        cached_result = wall_data['cached_result'] = {}

        profile_id = wall_data['request_profile_id']
        wall_profile_config_hash = None
        request_type = wall_data['request_type']

        if request_type in ['daily-ice-usage', 'costoverview/profile_id']:
            
            profile_config_hash_data = wall_data['profile_config_hash_data']
            wall_profile_config_hash = profile_config_hash_data[profile_id]

        try:
            if request_type == 'costoverview':
                self.fetch_wall_cost(wall_data, cached_result)
            elif request_type == 'costoverview/profile_id':
                self.fetch_wall_profile_cost(wall_profile_config_hash, cached_result)
            elif request_type == 'daily-ice-usage':
                self.fetch_daily_ice_usage(wall_data, profile_id, wall_profile_config_hash, cached_result)
        except (Wall.DoesNotExist, WallProfile.DoesNotExist, WallProfileProgress.DoesNotExist):
            return

    def fetch_wall_cost(self, wall_data: Dict[str, Any], cached_result: Dict[str, Any]) -> None:
        """
        # Fetch a cached Wall - both simulation types store the same cost
        """
        wall = Wall.objects.filter(wall_config_hash=wall_data['wall_config_hash']).first()
        if wall:
            cached_result['wall_total_cost'] = wall.total_cost

    def fetch_wall_profile_cost(self, wall_profile_config_hash: str | None, cached_result: Dict[str, Any]) -> None:
        """
        # Fetch a cached WallProfile - both simulation types store the same cost
        """
        if not wall_profile_config_hash:
            return
        wall_profile = WallProfile.objects.filter(wall_profile_config_hash=wall_profile_config_hash).first()
        if wall_profile:
            cached_result['wall_profile_cost'] = wall_profile.cost

    def fetch_daily_ice_usage(
            self, wall_data: Dict[str, Any], profile_id: str, wall_profile_config_hash: str | None, cached_result: Dict[str, Any]
    ) -> None:
        wall_progress_query_no_day = Q(
            wall_profile__wall__wall_config_hash=wall_data['wall_config_hash'],
            wall_profile__wall__num_crews=wall_data['num_crews'],
            wall_profile__wall_profile_config_hash=wall_profile_config_hash,
        )

        if wall_data['simulation_type'] == MULTI_THREADED:
            wall_progress_query_no_day &= Q(wall_profile__profile_id=profile_id)

        wall_progress_query_final = wall_progress_query_no_day & Q(day=wall_data['request_day'])

        try:
            wall_profile_progress = WallProfileProgress.objects.get(wall_progress_query_final)
            cached_result['profile_daily_ice_used'] = wall_profile_progress.ice_used
        except WallProfileProgress.DoesNotExist:
            self.check_if_cached_on_another_day(wall_data, wall_progress_query_no_day, profile_id)

    def check_if_cached_on_another_day(self, wall_data: Dict[str, Any], wall_progress_query_no_day: Q, profile_id: str) -> None:
        """
        Handles the case where daily ice usage is missing by checking if data exists for another day.
        """
        cached_on_another_day = WallProfileProgress.objects.filter(wall_progress_query_no_day).first()
        
        if cached_on_another_day:
            construction_days = cached_on_another_day.wall_profile.wall.construction_days
            if wall_data['request_day'] <= construction_days:
                response_details = f'No crew has worked on profile {profile_id} on day {wall_data["request_day"]}.'
                wall_data['error_response'] = Response(response_details, status=status.HTTP_404_NOT_FOUND)
            else:
                wall_data['error_response'] = self.create_out_of_range_response('day', construction_days, status.HTTP_400_BAD_REQUEST)
        else:
            raise WallProfileProgress.DoesNotExist

    def run_simulation_and_create_cache(self, wall_data: Dict[str, Any]) -> None:
        """
        Runs simulation, creates and saves the wall and its elements.
        """
        try:
            wall_construction = WallConstruction(
                wall_construction_config=wall_data['wall_construction_config'],
                sections_count=wall_data['sections_count'],
                num_crews=wall_data['num_crews'],
                simulation_type=wall_data['simulation_type']
            )
        except WallConstructionError as tech_error:
            wall_data['error_response'] = self.create_technical_error_response({}, tech_error)
            return
        wall_data['wall_construction'] = wall_construction
        wall_data['sim_calc_details'] = wall_construction.sim_calc_details
        self.store_simulation_result(wall_data)

        # Create the new cache data
        self.cache_wall(wall_data)
        if wall_data['error_response']:
            return

        # Validate if the day is correct with data from the simulation
        self.validate_day_within_range(wall_data)

    def store_simulation_result(self, wall_data):
        simulation_result = wall_data['simulation_result'] = {}

        # Used in the costowverview response
        simulation_result['wall_total_cost'] = wall_data['sim_calc_details']['total_cost']

        # Used in the costoverview/profile_id response
        request_profile_id = wall_data['request_profile_id']
        if request_profile_id:
            simulation_result['wall_profile_cost'] = wall_data['sim_calc_details']['profile_costs'][request_profile_id]

        # Used in the daily-ice-usage response
        request_day = wall_data['request_day']
        if request_day:
            profile_daily_progress_data = wall_data['sim_calc_details']['profile_daily_details'][request_profile_id]
            profile_day_data = profile_daily_progress_data.get(wall_data['request_day'], {})
            simulation_result['profile_daily_ice_used'] = profile_day_data.get('ice_used', 0)

    def cache_wall(self, wall_data: Dict[str, Any]) -> None:
        """
        Creates a new Wall object and saves it to the database.
        Starts a cascade cache creation of all wall elements.
        """
        total_cost = wall_data['sim_calc_details']['total_cost']
        try:
            wall = Wall.objects.create(
                wall_config_hash=wall_data['wall_config_hash'],
                num_crews=wall_data['num_crews'],
                total_cost=total_cost,
                construction_days=wall_data['sim_calc_details']['construction_days'],
            )
            self.process_wall_profiles(wall_data, wall, wall_data['simulation_type'])
        except IntegrityError as wall_crtn_hash_col_err:
            if (
                wall_data['num_crews'] == 0
                and 'unique constraint' in str(wall_crtn_hash_col_err)
                and 'wall_config_hash' in str(wall_crtn_hash_col_err)
            ):
                # Hash collision - should be a very rare case
                # TO DO: log hash collision tech. error in DB
                wall_data['error_response'] = self.create_technical_error_response({}, wall_crtn_hash_col_err)
        except Exception as wall_crtn_err_unkwn:
            # Other tech. error
            # TO DO: log tech. error in DB
            wall_data['error_response'] = self.create_technical_error_response({}, wall_crtn_err_unkwn)
            return

    def process_wall_profiles(self, wall_data: Dict[str, Any], wall: Wall, simulation_type: str = SINGLE_THREADED) -> None:
        """
        Processes the different behaviors for wall profiles caching in single and multi-threaded modes
        """
        cached_wall_profile_hashes = []

        for profile_id, profile_data in wall_data['wall_construction'].wall_profile_data.items():
            wall_profile_config_hash = wall_data['profile_config_hash_data'][profile_id]

            if simulation_type == SINGLE_THREADED:
                # Only cache the unique wall profile configs in single-threaded mode.
                # The build progress of the wall profiles with duplicate configs is
                # always the same.
                if wall_profile_config_hash in cached_wall_profile_hashes:
                    continue
                cached_wall_profile_hashes.append(wall_profile_config_hash)

            # Proceed to create the wall profile
            self.cache_wall_profile(wall, wall_data, profile_id, profile_data, wall_profile_config_hash, simulation_type)

    def cache_wall_profile(
            self, wall: Wall, wall_data: Dict[str, Any], profile_id: int, profile_data: Any,
            wall_profile_config_hash: str, simulation_type: str = SINGLE_THREADED
    ) -> None:
        """
        Creates a new WallProfile object and saves it to the database.
        Starting point for the wall profile progress caching..
        """
        wall_profile_creation_kwargs = {
            'wall': wall,
            'wall_profile_config_hash': wall_profile_config_hash,
            'cost': wall_data['sim_calc_details']['profile_costs'][profile_id],
        }

        # Set profile_id only for multi-threaded cases
        if simulation_type == MULTI_THREADED:
            wall_profile_creation_kwargs['profile_id'] = profile_id

        # Create the wall profile object
        wall_profile = WallProfile.objects.create(**wall_profile_creation_kwargs)

        # Proceed to create the wall profile progress
        self.cache_wall_profile_progress(wall_data, wall_profile, profile_id, profile_data)

    def cache_wall_profile_progress(self, wall_data: Dict[str, Any], wall_profile: WallProfile, profile_id: int, profile_data: dict) -> None:
        """
        Creates a new WallProfileProgress object and saves it to the database.
        """
        for day_index, data in profile_data.items():
            WallProfileProgress.objects.create(
                wall_profile=wall_profile,
                day=day_index,
                ice_used=data['ice_used']
            )

    def create_out_of_range_response(self, out_of_range_type: str, max_value: int | Any, status_code: int) -> Response:
        if out_of_range_type == 'day':
            finishing_msg = f'The wall has been finished for {max_value} days.'
        else:
            finishing_msg = f'The wall has {max_value} profiles.'
        response_details = {'error': f'The {out_of_range_type} is out of range. {finishing_msg}'}
        return Response(response_details, status=status_code)

    def create_technical_error_response(self, request_data, tech_error: Exception | None = None) -> Response:
        error_details = None
        if tech_error:
            tech_error_msg = str(tech_error.args[0])
            error_details = {'error_msg': tech_error_msg}
            if request_data:
                error_details['request_data'] = request_data
        error_msg = 'Wall Construction simulation failed. Please contact support.'
        error_response: Dict[str, Any] = {'error': error_msg}
        if error_details:
            error_response['error_details'] = error_details
        return Response({'error': error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class DailyIceUsageView(BaseWallProfileView):

    @extend_schema(
        summary='Get daily ice usage',
        description='Retrieve the amount of ice used on a specific day for a given wall profile.',
        parameters=daily_ice_usage_parameters,
        examples=daily_ice_usage_examples,
        responses=daily_ice_usage_responses
    )
    def get(self, request: HttpRequest, profile_id: int, day: int) -> Response:
        num_crews = request.GET.get('num_crews', 0)
        serializer = DailyIceUsageSerializer(data={'profile_id': profile_id, 'day': day, 'num_crews': num_crews})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile_id = serializer.validated_data['profile_id']    # type: ignore
        day = serializer.validated_data['day']                  # type: ignore
        num_crews = serializer.validated_data['num_crews']      # type: ignore

        wall_data = self.initialize_wall_data(profile_id, day)
        self.fetch_wall_data(wall_data, num_crews, profile_id, request_type='daily-ice-usage')
        if wall_data['error_response']:
            return wall_data['error_response']

        return self.build_daily_usage_response(wall_data, profile_id, day)

    def build_daily_usage_response(self, wall_data: Dict[str, Any], profile_id: int, day: int) -> Response:
        result_data = wall_data['cached_result']
        if not result_data:
            result_data = wall_data['simulation_result']
        profile_daily_ice_used = result_data['profile_daily_ice_used']
        response_data: Dict[str, Any] = {
            'profile_id': profile_id,
            'day': day,
        }
        if profile_daily_ice_used and isinstance(profile_daily_ice_used, int) and profile_daily_ice_used > 0:
            response_data['ice_used'] = profile_daily_ice_used
            response_data['details'] = f'Volume of ice used for profile {profile_id} on day {day}: {profile_daily_ice_used} cubic yards.'
            return Response(response_data, status=status.HTTP_200_OK)
        
        response_data['details'] = f'No crew has worked on profile {profile_id} on day {day}.'
        return Response(response_data, status=status.HTTP_404_NOT_FOUND)
    

class CostOverviewView(BaseWallProfileView):

    @extend_schema(
        operation_id='get_cost_overview',
        summary='Get cost overview',
        description='Retrieve the total wall construction cost.',
        parameters=[num_crews_parameter],
        examples=cost_overview_examples,
        responses=cost_overview_responses
    )
    def get(self, request: HttpRequest, profile_id: int | None = None) -> Response:
        num_crews = request.GET.get('num_crews', 0)
        request_data = {'profile_id': profile_id, 'num_crews': num_crews}
        cost_serializer = CostOverviewSerializer(data=request_data)
        if not cost_serializer.is_valid():
            return Response(cost_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile_id = cost_serializer.validated_data['profile_id']  # type: ignore
        num_crews = cost_serializer.validated_data['num_crews']  # type: ignore

        request_type = 'costoverview' if not profile_id else 'costoverview/profile_id'

        wall_data = self.initialize_wall_data(profile_id, None)
        self.fetch_wall_data(wall_data, num_crews, profile_id, request_type)
        if wall_data['error_response']:
            return wall_data['error_response']
        
        return self.build_cost_overview_response(wall_data, profile_id)

    def build_cost_overview_response(self, wall_data: Dict[str, Any], profile_id: int | None) -> Response:
        result_data = wall_data['cached_result']
        if not result_data:
            result_data = wall_data['simulation_result']
        if profile_id is None:
            wall_total_cost = result_data['wall_total_cost']
            response_data = {
                'total_cost': f'{wall_total_cost:.0f}',
                'details': f'Total construction cost: {wall_total_cost:.0f} Gold Dragon coins',
            }
        else:
            wall_profile_cost = result_data['wall_profile_cost']
            response_data = {
                'profile_id': profile_id,
                'profile_cost': f'{wall_profile_cost:.0f}',
                'details': f'Profile {profile_id} construction cost: {wall_profile_cost:.0f} Gold Dragon coins',
            }
        return Response(response_data, status=status.HTTP_200_OK)


class CostOverviewProfileidView(CostOverviewView):

    @extend_schema(
        operation_id='get_cost_overview_profile_id',
        summary='Get cost overview for a profile',
        description='Retrieve the total cost for a specific wall profile.',
        parameters=cost_overview_parameters + [num_crews_parameter],
        examples=cost_overview_profile_id_examples,
        responses=cost_overview_responses
    )
    def get(self, request: HttpRequest, profile_id: int | None = None) -> Response:
        return super().get(request, profile_id)


def custom_404_view(request, exception=None):
    """
    Custom 404 view for the API. Returns a JSON response with an error message
    and a list of available endpoints.
    """
    if request.path.startswith('/api'):
        available_endpoints = [
            endpoint['path'].replace('<', '{').replace('>', '}')
            for endpoint in exposed_endpoints.values()
        ]

        response_data = {
            'error': 'Endpoint not found',
            'error_details': 'The requested API endpoint does not exist. Please use the available endpoints.',
            'available_endpoints': available_endpoints,
        }
        return JsonResponse(response_data, status=404)
    else:
        return page_not_found(request, exception, template_name='404.html')
