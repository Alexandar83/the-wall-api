from decimal import Decimal
from typing import Iterable

from django.conf import settings
from django.db.models import QuerySet
from django.http import HttpRequest, JsonResponse
from django.views.defaults import page_not_found

from drf_spectacular.utils import extend_schema

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from the_wall_api.models import SimulationResult, WallProfile
from the_wall_api.serializers import CostOverviewRequestSerializer, DailyIceUsageRequestSerializer
from the_wall_api.utils import (
    MULTI_THREADED, SINGLE_THREADED, WallConstructionError, WallProfileResponse,
    exposed_endpoints, generate_config_hash, load_wall_profiles_from_config,
    daily_ice_usage_parameters, daily_ice_usage_examples, daily_ice_usage_responses,
    cost_overview_parameters, cost_overview_examples, cost_overview_responses, num_crews_parameter
)
from the_wall_api.wall_construction import WallConstruction


ICE_COST_PER_CUBIC_YARD = settings.ICE_COST_PER_CUBIC_YARD      # Gold dragons cost per cubic yard


class BaseWallProfileView(APIView):

    def get_wall_profiles(
        self, profile_id: int | None = None, day: int | None = None, num_crews: int = 0
    ) -> WallProfileResponse:
        default_response_tuple = [], None
        
        # Retreive wall configuration
        try:
            wall_profiles_config = load_wall_profiles_from_config()
        except (WallConstructionError, FileNotFoundError) as tech_error:
            return WallProfileResponse(
                self.create_technical_error_response({}, tech_error), *default_response_tuple
            )

        # Profile number validation
        max_profile_number = len(wall_profiles_config)
        if profile_id is not None and profile_id > max_profile_number:
            return WallProfileResponse(
                self.create_out_of_range_response('profile number', max_profile_number, status.HTTP_400_BAD_REQUEST), *default_response_tuple
            )

        # Simulation parameters
        simulation_type, config_hash, profile_id_list = self.evaluate_simulation_params(
            num_crews, wall_profiles_config, profile_id, max_profile_number
        )
                
        # Collect cached data
        wall_profile_items = self.collect_cached_wall_profiles(config_hash, profile_id_list, num_crews)

        error_response = None
        if wall_profile_items.count() != len(profile_id_list):
            # No cached data - run a simulation
            error_response, wall_profile_items = self.run_simulation_and_save(
                wall_profiles_config, simulation_type, num_crews, profile_id_list, day, config_hash
            )
        elif day is not None:
            # If a 'day' is provided in the request, validate its consistency against the cached simulation data
            error_response = self.validate_day_within_range(wall_profile_items, day)

        if error_response:
            return WallProfileResponse(error_response, *default_response_tuple)

        return WallProfileResponse(
            error_response=None, wall_profiles=wall_profile_items, simulation_type=simulation_type,
        )

    def create_out_of_range_response(self, out_of_range_type: str, max_value: int, status_code: int) -> Response:
        response_details = {'error': f'The {out_of_range_type} is out of range. The maximum value is {max_value}.'}
        return Response(response_details, status=status_code)

    def evaluate_simulation_params(
            self, num_crews: int | None, wall_profiles_config: list, profile_id: int | None, max_profile_number: int
    ) -> tuple[str, str, list[int]]:
        # Determine the simulation type based on num_crews
        
        simulation_type = MULTI_THREADED if num_crews else SINGLE_THREADED
        
        config_hash = generate_config_hash(wall_profiles_config, num_crews)
        
        if profile_id is not None:
            # daily ice usage or cost overview for a single profile
            profile_id_list = [profile_id]
        else:
            # total cost overview - all profiles are requred
            profile_id_list = list(range(1, max_profile_number + 1))

        return simulation_type, config_hash, profile_id_list

    def collect_cached_wall_profiles(self, config_hash: str, profile_id_list: list, num_crews: int | None) -> QuerySet[WallProfile]:
        """
        *Single profile_id request: daily ice usage OR cost overview endpoints
        -For both simulation types a single DB match for the wall profile ensures there is a cached simulation data
            -single_threaded: because there's no variation introduced from the num_crews
            -multi_threaded: because the query includes the num_crews, to cover for the variation
        *No profile_id request: cost overview endpoint
        -For both simulation types all profiles need to be found in the DB to ensure there's a cached simulation data
        **Possible further optimization: for singlethreaded one DB match would actually be enough
        """
        wall_profile_items = WallProfile.objects.filter(
            config_hash=config_hash,
            wall_config_profile_id__in=profile_id_list,
            num_crews=num_crews
        )
        return wall_profile_items
    
    def validate_day_within_range(self, wall_profile_items: QuerySet[WallProfile], day: int) -> Response | None:
        wall_profile = wall_profile_items.first()
        if wall_profile and day > wall_profile.max_day:
            return self.create_out_of_range_response('day', wall_profile.max_day, status.HTTP_400_BAD_REQUEST)
        return None

    def run_simulation_and_save(
        self, wall_profiles_config: list, simulation_type: str, num_crews: int, profile_id_list: list, day: int | None, config_hash: str
    ) -> tuple[Response | None, list[WallProfile]]:
        """
        Runs a wall profile build simulation for each profile
        in profile_id_listand commits the results to the DB
        """
        request_data = {'profile_id_list': profile_id_list, 'day': day, 'num_crews': num_crews}

        try:
            wall_construction = WallConstruction(wall_profiles_config, num_crews, simulation_type)
        except WallConstructionError as tech_error:
            return self.create_technical_error_response(request_data, tech_error), []

        # Calculate the max day for request data validation and caching purposes
        max_day = 0
        for days_data in wall_construction.wall_profile_data.values():
            max_day = max(max_day, max(days_data.keys()))
        
        created_wall_profiles = []
        try:
            for profile_index in profile_id_list:
                created_wall_profiles.append(self.create_and_save_wall_profile(profile_index, config_hash, num_crews, wall_construction, simulation_type, max_day))
        except KeyError as key_err:
            return self.create_technical_error_response(request_data, key_err), []
                
        # The simulation is valid and remains cached for the next valid day input
        if day is not None and day > max_day:
            return self.create_out_of_range_response('day', max_day, status.HTTP_400_BAD_REQUEST), []
                
        return None, created_wall_profiles
    
    def create_technical_error_response(self, request_data, tech_error: Exception) -> Response:
        tech_error_msg = f'{str(tech_error.args[0])}'
        error_details = {
            'error_msg': tech_error_msg
        }
        if request_data:
            error_details['request_data'] = request_data
        error_msg = 'Wall Construction simulation failed. Please contact support.'
        return Response({'error': error_msg, 'error_details': error_details}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    def create_and_save_wall_profile(
        self, profile_index: int, config_hash: str, num_crews: int, wall_construction: WallConstruction, simulation_type: str, max_day: int
    ) -> WallProfile:
        try:
            profile_data = wall_construction.wall_profile_data[profile_index]
        except KeyError as key_err:
            raise KeyError(f'Wall Construction simulation failed. {profile_index}') from key_err
        wall_profile = WallProfile.objects.create(
            wall_config_profile_id=profile_index,
            config_hash=config_hash,
            num_crews=num_crews,
            max_day=max_day
        )
        self.create_and_save_simulation_results(wall_profile, profile_data, simulation_type)
        return wall_profile

    def create_and_save_simulation_results(self, wall_profile: WallProfile, profile_data: dict, simulation_type: str) -> None:
        for day_index, data in profile_data.items():
            SimulationResult.objects.create(
                wall_profile=wall_profile,
                day=day_index,
                ice_used=data['ice_used'],
                cost=Decimal(data['ice_used']) * Decimal(ICE_COST_PER_CUBIC_YARD),
                simulation_type=simulation_type
            )

    def get_wall_profile_max_num_crews(self, wall_profile_items: Iterable[WallProfile], num_crews: int | None) -> int | None:
        if num_crews:
            for wall_profile in wall_profile_items:
                if wall_profile:
                    wall_profile_num_crews = getattr(wall_profile, 'num_crews', 0)
                    num_crews = max(num_crews, wall_profile_num_crews)
                    return num_crews
                else:
                    return 0
        
        return 0


class DailyIceUsageView(BaseWallProfileView):

    @extend_schema(
        summary='Get daily ice usage',
        description='Retrieve the amount of ice used on a specific day for a given wall profile.',
        parameters=daily_ice_usage_parameters,
        examples=daily_ice_usage_examples,
        responses=daily_ice_usage_responses
    )
    def get(self, request: HttpRequest, profile_id: int, day: int) -> Response:
        """
        Retrieves the amount of ice used in a wall profile on a specific day,
        or returns an error if not found.

        URL Parameters:
            - profile_id (int): The wall profile's ID.
            - day (int): The specific day for the ice usage.

        Responses:
            - 200 OK: Ice usage data for a day.
            - 400 BAD REQUEST: Invalid input.
            - 500 INTERNAL SERVER ERROR: Simulation data inconsistency.
        """
        num_crews = request.GET.get('num_crews')
        serializer = DailyIceUsageRequestSerializer(data={'profile_id': profile_id, 'day': day, 'num_crews': num_crews})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        # REF-1: The validated_data is dynamically transformed into a dict after the validation
        profile_id = serializer.validated_data['profile_id']    # type: ignore
        day = serializer.validated_data['day']                  # type: ignore
        num_crews = serializer.validated_data['num_crews']      # type: ignore
        
        # Fetch wall profiles and handle potential errors
        error_response, wall_profile_items, simulation_type = self.get_wall_profiles(profile_id, day, num_crews)
        if error_response:
            return error_response
        
        request_data = {'profile_id': profile_id, 'day': day, 'num_crews': num_crews}
        # Always one profile
        # wall_profile_items: Iterable[WallProfile] - for is used here for unpacking
        inconsistency_error_msg = 'Simulation data inconsistency detected. Please contact support.'
        for wall_profile in wall_profile_items:
            try:
                simulation_result = SimulationResult.objects.get(
                    wall_profile=wall_profile,
                    day=int(day),
                    simulation_type=simulation_type
                )
                return self.build_daily_usage_valid_response(profile_id, day, simulation_result)
            except SimulationResult.DoesNotExist:
                return Response(
                    {'error': inconsistency_error_msg, 'error_details': request_data},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
        
        return Response(
            {'error': inconsistency_error_msg, 'error_details': request_data},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

    def build_daily_usage_valid_response(self, profile_id: int, day: int, simulation_result: SimulationResult) -> Response:
        response_data = {
            'profile_id': profile_id,
            'day': day,
            'ice_amount': simulation_result.ice_used,
            'details': f'Volume of ice used for profile {profile_id} on day {day}: {simulation_result.ice_used} cubic yards.',
        }
        return Response(response_data, status=status.HTTP_200_OK)


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
        """
        Provides an overview of the total cost for one or more wall profiles.

        URL Parameter:
            - profile_id (int, optional): The wall profile's ID.

        Responses:
            - 200 OK: Total cost and detailed results.
            - 400 BAD REQUEST: Invalid input.
            - 500 INTERNAL SERVER ERROR: Simulation data inconsistency.
        """
        num_crews = request.GET.get('num_crews')
        cost_serializer = CostOverviewRequestSerializer(data={'profile_id': profile_id, 'num_crews': num_crews})
        if not cost_serializer.is_valid():
            return Response(cost_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        profile_id = cost_serializer.validated_data['profile_id']       # type: ignore - See REF-1
        num_crews = cost_serializer.validated_data['num_crews']         # type: ignore
        
        error_response, wall_profile_items, _ = self.get_wall_profiles(profile_id=profile_id, num_crews=num_crews)
        if error_response:
            return error_response

        simulation_results = SimulationResult.objects.filter(wall_profile__in=wall_profile_items)

        total_cost = Decimal(0) + sum(result.cost for result in simulation_results)
        return self.build_cost_overview_valid_response(profile_id, total_cost)
    
    def build_cost_overview_valid_response(self, profile_id: int | None, total_cost: Decimal | int,) -> Response:
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
        # The request path starts with the API root
        
        # Collect and make the endpoint paths URL-safe
        available_endpoints = []
        for endpoint in exposed_endpoints.values():
            safe_path = endpoint['path'].replace('<', '{').replace('>', '}')
            available_endpoints.append(safe_path)

        response_data = {
            'error': 'Endpoint not found',
            'error_details': 'The requested API endpoint does not exist. Please use the available endpoints.',
            'available_endpoints': available_endpoints
        }
        return JsonResponse(response_data, status=404)
    else:
        # Fallback to Django's default 404 view
        return page_not_found(request, exception, template_name='404.html')
