from typing import Any, Dict

from django.http import HttpRequest, JsonResponse
from django.views.defaults import page_not_found
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from the_wall_api.serializers import CostOverviewSerializer, DailyIceUsageSerializer
from the_wall_api.utils import api_utils
from the_wall_api.utils.storage_utils import fetch_wall_data
from the_wall_api.wall_construction import initialize_wall_data


class DailyIceUsageView(APIView):

    @extend_schema(
        tags=['daily-ice-usage'],
        summary='Get daily ice usage',
        description='Retrieve the amount of ice used on a specific day for a given wall profile.',
        parameters=api_utils.daily_ice_usage_parameters + [api_utils.num_crews_parameter],
        examples=api_utils.daily_ice_usage_examples,
        responses=api_utils.daily_ice_usage_responses
    )
    def get(self, request: HttpRequest, profile_id: int, day: int) -> Response:
        num_crews = request.GET.get('num_crews', 0)
        serializer = DailyIceUsageSerializer(data={'profile_id': profile_id, 'day': day, 'num_crews': num_crews})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile_id = serializer.validated_data['profile_id']    # type: ignore
        day = serializer.validated_data['day']                  # type: ignore
        num_crews = serializer.validated_data['num_crews']      # type: ignore

        wall_data = initialize_wall_data(profile_id, day)
        fetch_wall_data(wall_data, num_crews, profile_id, request_type='daily-ice-usage')
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
    

class CostOverviewView(APIView):

    @extend_schema(
        tags=['cost-overview'],
        operation_id='get_cost_overview',
        summary='Get cost overview',
        description='Retrieve the total wall construction cost.',
        parameters=[api_utils.num_crews_parameter],
        examples=api_utils.cost_overview_examples,
        responses=api_utils.cost_overview_responses
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

        wall_data = initialize_wall_data(profile_id, None)
        fetch_wall_data(wall_data, num_crews, profile_id, request_type)
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
        tags=['cost-overview'],
        operation_id='get_cost_overview_profile_id',
        summary='Get cost overview for a profile',
        description='Retrieve the total cost for a specific wall profile.',
        parameters=api_utils.cost_overview_parameters + [api_utils.num_crews_parameter],
        examples=api_utils.cost_overview_profile_id_examples,
        responses=api_utils.cost_overview_responses
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
            for endpoint in api_utils.exposed_endpoints.values()
        ]

        response_data = {
            'error': 'Endpoint not found',
            'error_details': 'The requested API endpoint does not exist. Please use the available endpoints.',
            'available_endpoints': available_endpoints,
        }
        return JsonResponse(response_data, status=404)
    else:
        return page_not_found(request, exception, template_name='404.html')
