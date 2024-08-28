import copy
from decimal import Decimal
from typing import Any, Dict

from django.conf import settings
from django.http import HttpRequest, JsonResponse
from django.views.defaults import page_not_found

from drf_spectacular.utils import extend_schema

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from the_wall_api.models import WallProfileProgress, WallProfile, Wall
from the_wall_api.serializers import CostOverviewRequestSerializer, DailyIceUsageRequestSerializer
from the_wall_api.utils import (
    MULTI_THREADED, SINGLE_THREADED, WallConstructionError,
    exposed_endpoints, generate_config_hash_details, load_wall_profiles_from_config,
    daily_ice_usage_parameters, daily_ice_usage_examples, daily_ice_usage_responses,
    cost_overview_parameters, cost_overview_examples, cost_overview_responses, num_crews_parameter
)
from the_wall_api.wall_construction import WallConstruction


ICE_COST_PER_CUBIC_YARD = settings.ICE_COST_PER_CUBIC_YARD  # Gold dragons cost per cubic yard


class BaseWallProfileView(APIView):

    def fetch_wall_data(
        self, wall_data: Dict[str, Any], profile_id: int | None = None, day: int | None = None, num_crews: int = 0, request_type: str = ''
    ):
        wall_construction_config = self.get_wall_construction_config(wall_data)
        if wall_data['error_response']:
            return

        if self.is_invalid_profile_number(profile_id, wall_construction_config, wall_data):
            return

        self.set_simulation_params(wall_data, num_crews, wall_construction_config, profile_id, day, request_type)
        
        if self.is_invalid_wall_profile_config(wall_data):
            return
        
        # Check for cached data
        self.collect_cached_data(wall_data, request_type)
        if wall_data['error_response']:
            return
        
        self.validate_day_within_range(wall_data)
        if wall_data['error_response']:
            return

        # If no cached data is found, run the simulation
        if not wall_data.get('cached_result'):
            wall_data['error_response'] = self.run_simulation_and_save(wall_data)
            if wall_data['error_response']:
                return

    def initialize_wall_data(self, profile_id: int | None = None, day: int | None = None, num_crews: int = 0) -> Dict[str, Any]:
        """
        Initialize the wall_data dictionary to hold various control data
        throughout the wall construction process.
        """
        return {
            'profile_id': profile_id,
            'day': day,
            'num_crews': num_crews,
            'error_response': None,
            'simulation_type': None,
            'wall': None,
            'wall_construction': None,
            'wall_config_hash': None,
            'profile_config_hash_list': None,
            'wall_profile': None,
        }

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
            self, wall_data: Dict[str, Any], num_crews: int, wall_construction_config: list,
            profile_id: int | None, day: int | None, request_type: str
    ):
        """Set the simulation parameters for the wall_data dictionary."""
        simulation_type, wall_config_hash_details = self.evaluate_simulation_params(
            num_crews, wall_construction_config, profile_id
        )
        wall_data['wall_construction_config'] = copy.deepcopy(wall_construction_config)
        wall_data['simulation_type'] = simulation_type
        wall_data['wall_config_hash'] = wall_config_hash_details['wall_config_hash']
        wall_data['profile_config_hash_list'] = wall_config_hash_details['profile_config_hash_list']
        wall_data['request_type'] = request_type
        
    def is_invalid_wall_profile_config(self, wall_data: Dict[str, Any]):
        if wall_data['request_type'] in ['daily-ice-usage', 'costoverview/profile_id']:
            if wall_data['simulation_type'] == SINGLE_THREADED and not wall_data['profile_config_hash_list']:
                wall_data['error_response'] = self.create_technical_error_response({})
                return True

    def validate_day_within_range(self, wall_data: Dict[str, Any]):
        """Validate the provided day against the (cached) simulation data."""
        max_day = None
        already_simulated = wall_data.get('wall_construction')
        if already_simulated:
            # Calculate from simulated data
            max_day = self.get_max_day(wall_data['wall_construction'])
            wall_data['max_day'] = max_day
        elif wall_data.get('wall_profile'):
            max_day = wall_data['wall_profile'].max_day
        if None not in [max_day, wall_data['day']] and wall_data['day'] > max_day:
            wall_data['error_response'] = self.create_out_of_range_response('day', max_day, status.HTTP_400_BAD_REQUEST)

    def evaluate_simulation_params(
        self, num_crews: int | None, wall_construction_config: list, profile_id: int | None
    ) -> tuple[str, dict]:
        simulation_type = MULTI_THREADED if num_crews else SINGLE_THREADED

        wall_config_hash_details = generate_config_hash_details(wall_construction_config)

        return simulation_type, wall_config_hash_details

    def collect_cached_data(
        self, wall_data: Dict[str, Any], request_type: str
    ) -> Response | None:
        """
        Checks for different type of cached data, based on the request type.
        **MULTI_THREADED:
        -Only wall caching
        **SINGLE_THREADED:
        -All types of DB objects are cached
        """
        # No profile_id is sent for costoverview
        wall_profile_config_hash = None
        request_type = wall_data['request_type']
        profile_config_hash_list = []
        if request_type in ['daily-ice-usage', 'costoverview/profile_id']:
            # There's no profile_id for costoverview
            profile_config_hash_list = wall_data.get('profile_config_hash_list', [])
            wall_profile_config_hash = profile_config_hash_list[wall_data['profile_id'] - 1]
            
        try:
            if request_type == 'costoverview':
                # Fetch a Wall - both simulation types store the needed data
                wall = Wall.objects.get(wall_config_hash=wall_data['wall_config_hash'])
                wall_data['cached_result'] = wall
                wall_data['wall_total_cost'] = wall.total_cost
            elif wall_data['simulation_type'] == SINGLE_THREADED:
                if request_type == 'costoverview/profile_id':
                    # Fetch a WallProfile
                    wall_profile = WallProfile.objects.get(
                        wall_profile_config_hash=wall_profile_config_hash,
                    )
                    wall_data['cached_result'] = wall_profile
                    wall_data['wall_profile'] = wall_profile
                    wall_data['wall_profile_cost'] = wall_profile.cost
                elif request_type == 'daily-ice-usage':
                    # Fetch a WallProfileProgress
                    wall_profile_progress = WallProfileProgress.objects.filter(
                        wall_profile__wall_profile_config_hash__in=profile_config_hash_list,
                        day=wall_data['day']
                    ).first()
                    if wall_profile_progress is None:
                        raise WallProfileProgress.DoesNotExist
                    wall_data['cached_result'] = wall_profile_progress
                    wall_data['profile_daily_ice_used'] = wall_profile_progress.ice_used
        except (Wall.DoesNotExist, WallProfile.DoesNotExist, WallProfileProgress.DoesNotExist):
            return

        return

    def run_simulation_and_save(self, wall_data: Dict[str, Any]):
        """
        Runs simulation, creates and saves the wall and its elements,
        and adds them to the wall_data.
        """
        try:
            wall_construction = WallConstruction(wall_data['wall_construction_config'], wall_data['num_crews'], wall_data['simulation_type'])
        except WallConstructionError as tech_error:
            return self.create_technical_error_response({}, tech_error)
        wall_data['wall_construction'] = wall_construction

        # Validate the day is correct with data from a simulation
        self.validate_day_within_range(wall_data)
        if wall_data['error_response']:
            return wall_data['error_response']

        # Create the new cache data
        self.create_and_save_wall(wall_construction, wall_data)

    def get_max_day(self, wall_construction: WallConstruction) -> int:
        """Calculate the maximum day across all profiles in the construction data."""
        max_day = 0
        for days_data in wall_construction.wall_profile_data.values():
            max_day = max(max_day, max(days_data.keys()))
        return max_day

    def create_and_save_wall(self, wall_construction: WallConstruction, wall_data: Dict[str, Any]):
        wall_data['sim_calc_details'] = wall_construction._sim_calc_details()
        total_cost = wall_data['sim_calc_details']['total_cost']
        wall = Wall.objects.filter(wall_config_hash=wall_data['wall_config_hash']).first()
        if not wall:
            wall = Wall.objects.create(
                wall_config_hash=wall_data['wall_config_hash'],
                total_cost=total_cost,
            )
        wall_data['wall'] = wall
        wall_data['wall_total_cost'] = wall.total_cost
        
        if wall_data['simulation_type'] == SINGLE_THREADED:
            # Create wall profiles and profile progress records only for single-threaded mode
            # until there is a way to ensure results consistency for multi-threaded mode
            self.create_and_save_wall_profiles(wall_data)

    def create_and_save_wall_profiles(self, wall_data: Dict[str, Any]):
        wall_data['wall_profiles_data'] = {}

        for profile_id, profile_data in wall_data['wall_construction'].wall_profile_data.items():
            wall_profile_config_hash = wall_data['profile_config_hash_list'][profile_id - 1]
            wall_profile = WallProfile.objects.filter(
                wall_profile_config_hash=wall_profile_config_hash
            ).first()
            if not wall_profile:
                wall_profile = WallProfile.objects.create(
                    wall_profile_config_hash=wall_profile_config_hash,
                    cost=wall_data['sim_calc_details']['profile_costs'][profile_id],
                    max_day=wall_data['max_day']
                )
            self.create_and_save_wall_profile_progress(
                wall_data, wall_profile, profile_id, wall_profile_config_hash, profile_data
            )

    def create_and_save_wall_profile_progress(
            self, wall_data: Dict[str, Any], wall_profile: WallProfile, profile_id: int, wall_profile_config_hash: str, profile_data: dict
    ) -> None:
        profile_progress_data = wall_data['wall_profiles_data'].setdefault(profile_id, {})

        for day_index, data in profile_data.items():
            wall_profile_progress = WallProfileProgress.objects.filter(
                wall_profile=wall_profile,
                day=day_index
            ).first()
            if not wall_profile_progress:
                wall_profile_progress = WallProfileProgress.objects.create(
                    wall_profile=wall_profile,
                    day=day_index,
                    ice_used=data['ice_used'],
                    cost=Decimal(data['ice_used']) * Decimal(ICE_COST_PER_CUBIC_YARD),
                )
            wall_data['profile_daily_ice_used'] = wall_profile_progress.ice_used
            profile_progress_data[day_index] = {
                'ice_used': wall_profile_progress.ice_used,
                'cost': wall_profile_progress.cost
            }

    def create_out_of_range_response(self, out_of_range_type: str, max_value: int | Any, status_code: int) -> Response:
        response_details = {'error': f'The {out_of_range_type} is out of range. The maximum value is {max_value}.'}
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
        num_crews = request.GET.get('num_crews')
        serializer = DailyIceUsageRequestSerializer(data={'profile_id': profile_id, 'day': day, 'num_crews': num_crews})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile_id = serializer.validated_data['profile_id']  # type: ignore
        day = serializer.validated_data['day']  # type: ignore
        num_crews = serializer.validated_data['num_crews']  # type: ignore

        wall_data = self.initialize_wall_data(profile_id, day, num_crews)
        self.fetch_wall_data(wall_data, profile_id, day, num_crews, request_type='daily-ice-usage')
        if wall_data['error_response']:
            return wall_data['error_response']

        return self.build_daily_usage_response(wall_data, profile_id, day, str(wall_data['simulation_type']))

    def build_daily_usage_response(
        self, wall_data: Dict[str, Any], profile_id: int, day: int, simulation_type: str
    ) -> Response:
        ice_used, response_status = self.get_final_result(wall_data)
        response_data: Dict[str, Any] = {'profile_id': profile_id, 'day': day, 'simulation_type': simulation_type}
        if response_status == status.HTTP_200_OK:
            response_data['ice_used'] = ice_used
            response_data['details'] = f'Volume of ice used for profile {profile_id} on day {day}: {ice_used} cubic yards.'
        elif response_status == status.HTTP_404_NOT_FOUND:
            response_data['details'] = f'No crew has worked on profile {profile_id} on day {day}.'
        elif response_status == status.HTTP_500_INTERNAL_SERVER_ERROR:
            response_data['error'] = 'Simulation data inconsistency detected. Please contact support.'
        return Response(response_data, status=response_status)

    def get_final_result(self, wall_data: Dict[str, Any]) -> tuple[int | None, int]:
        """Retrieve ice usage for the given profile and day."""
        profile_daily_ice_used = wall_data.get('profile_daily_ice_used')
        if profile_daily_ice_used and isinstance(profile_daily_ice_used, int) and profile_daily_ice_used > 0:
            return profile_daily_ice_used, status.HTTP_200_OK
            
        wall_construction = wall_data.get('wall_construction')
        if wall_construction:
            ice_used = wall_construction.wall_profile_data.get(wall_data['profile_id'], {}).get(wall_data['day'], {}).get('ice_used', 0)
            if ice_used > 0:
                return ice_used, status.HTTP_200_OK

        return None, status.HTTP_404_NOT_FOUND
    

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
        num_crews = request.GET.get('num_crews')
        request_data = {'profile_id': profile_id, 'num_crews': num_crews}
        cost_serializer = CostOverviewRequestSerializer(data=request_data)
        if not cost_serializer.is_valid():
            return Response(cost_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile_id = cost_serializer.validated_data['profile_id']  # type: ignore
        num_crews = cost_serializer.validated_data['num_crews']  # type: ignore

        request_type = 'costoverview' if not profile_id else 'costoverview/profile_id'

        wall_data = self.initialize_wall_data(profile_id, None, num_crews)
        self.fetch_wall_data(wall_data, profile_id=profile_id, num_crews=num_crews, request_type=request_type)
        if wall_data['error_response']:
            return wall_data['error_response']
        
        total_cost = None
        if wall_data['request_type'] == 'costoverview':
            total_cost = wall_data.get('wall_total_cost')
        elif wall_data['simulation_type'] == SINGLE_THREADED:
            total_cost = wall_data.get('wall_profile_cost')
        if total_cost is None:
            total_cost = wall_data.get('sim_calc_details', {}).get('profile_costs', {}).get(profile_id)

        if total_cost is None:
            return self.create_technical_error_response(request_data)

        return self.build_cost_overview_response(profile_id, total_cost)

    def build_cost_overview_response(self, profile_id: int | None, total_cost: Decimal | int,) -> Response:
        if profile_id is None:
            response_data = {
                'total_cost': f'{total_cost:.0f}',
                'details': f'Total construction cost: {total_cost:.0f} Gold Dragon coins',
            }
        else:
            response_data = {
                'profile_id': profile_id,
                'profile_cost': f'{total_cost:.0f}',
                'details': f'Profile {profile_id} construction cost: {total_cost:.0f} Gold Dragon coins',
            }
        return Response(response_data, status=status.HTTP_200_OK)


class CostOverviewProfileidView(CostOverviewView):

    @extend_schema(
        operation_id='get_cost_overview_profile_id',
        summary='Get cost overview for a profile',
        description='Retrieve the total cost for a specific wall profile.',
        parameters=cost_overview_parameters + [num_crews_parameter],
        examples=cost_overview_examples,
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
            'available_endpoints': available_endpoints
        }
        return JsonResponse(response_data, status=404)
    else:
        return page_not_found(request, exception, template_name='404.html')
