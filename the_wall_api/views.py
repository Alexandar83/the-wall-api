from typing import Any, Dict

from django.http import HttpRequest, JsonResponse
from django.views.defaults import page_not_found
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authentication import TokenAuthentication
from rest_framework.permissions import IsAuthenticated

from the_wall_api.serializers import (
    CostOverviewSerializer, DailyIceUsageSerializer, WallConfigFileUploadSerializer
)
from the_wall_api.utils import api_utils
from the_wall_api.utils.open_api_schema_utils import (
    open_api_parameters, open_api_resposnes, open_api_schemas
)
from the_wall_api.utils.storage_utils import (
    fetch_user_wall_config_files, fetch_wall_data, manage_wall_config_file_upload
)
from the_wall_api.wall_construction import initialize_wall_data


class WallConfigFileUploadView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = WallConfigFileUploadSerializer

    @extend_schema(
        tags=['wallconfig-files'],
        summary='Upload Wall Configuration File',
        description=(
            'Allows users to upload wall configuration files, which are '
            'parsed and stored as structured data in the database. \n\nThe processed data can be '
            'accessed through the `daily-ice-usage`, `cost-overview`, and `cost-overview-profile` endpoints.'
        ),
        request=open_api_schemas.wallconfig_file_upload_schema,
        responses=open_api_resposnes.wallconfig_file_upload_responses
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        config_id = serializer.validated_data['config_id']                      # type: ignore
        wall_config_file_data = serializer.context['wall_config_file_data']     # type: ignore

        wall_data = {
            'request_type': 'wallconfig-files/upload',
            'user': request.user,
            'initial_wall_construction_config': wall_config_file_data,
            'config_id': config_id,
            'error_response': None
        }
        manage_wall_config_file_upload(wall_data)
        if wall_data['error_response']:
            return wall_data['error_response']

        return self.build_upload_response(config_id)

    def build_upload_response(self, config_id):
        response_data = {
            'config_id': config_id,
            'details': f'Wall config <{config_id}> uploaded successfully.'
        }

        return Response(response_data, status=status.HTTP_201_CREATED)


class WallConfigFileListView(APIView):
    authentication_classes = [TokenAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=['wallconfig-files'],
        summary='List Wall Configuration Files',
        description='Retrieve a list of wall configuration files uploaded by the user.',
        responses=open_api_resposnes.wallconfig_file_list_responses
    )
    def get(self, request):
        wall_data = {
            'request_type': 'wallconfig-files/list',
            'user': request.user,
            'error_response': None
        }
        config_id_list = fetch_user_wall_config_files(wall_data)
        if wall_data['error_response']:
            return wall_data['error_response']

        response_data = {
            'config_id_list': config_id_list
        }
        return Response(response_data, status=status.HTTP_200_OK)


class DailyIceUsageView(APIView):
    authentication_classes = []

    @extend_schema(
        tags=['daily-ice-usage'],
        summary='Get Daily Ice Usage',
        description='Retrieve the amount of ice used on a specific day for a given wall profile.',
        parameters=open_api_parameters.daily_ice_usage_parameters + [open_api_parameters.num_crews_parameter],
        responses=open_api_resposnes.daily_ice_usage_responses
    )
    def get(self, request: HttpRequest, profile_id: int, day: int) -> Response:
        request_num_crews = api_utils.get_request_num_crews(request)
        num_crews = request.GET.get('num_crews', 0)
        serializer = DailyIceUsageSerializer(data={'profile_id': profile_id, 'day': day, 'num_crews': num_crews})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile_id = serializer.validated_data['profile_id']    # type: ignore
        day = serializer.validated_data['day']                  # type: ignore
        num_crews = serializer.validated_data['num_crews']      # type: ignore

        wall_data = initialize_wall_data(profile_id, day, request_num_crews)
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
    authentication_classes = []

    @extend_schema(
        tags=['cost-overview'],
        operation_id='get_cost_overview',
        summary='Get Cost Overview',
        description='Retrieve the total wall construction cost.',
        parameters=[open_api_parameters.num_crews_parameter],
        responses=open_api_resposnes.cost_overview_responses
    )
    def get(self, request: HttpRequest, profile_id: int | None = None) -> Response:
        request_num_crews = api_utils.get_request_num_crews(request)
        num_crews = request.GET.get('num_crews', 0)
        request_data = {'profile_id': profile_id, 'num_crews': num_crews}
        cost_serializer = CostOverviewSerializer(data=request_data)
        if not cost_serializer.is_valid():
            return Response(cost_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        profile_id = cost_serializer.validated_data['profile_id']  # type: ignore
        num_crews = cost_serializer.validated_data['num_crews']  # type: ignore

        request_type = 'costoverview' if not profile_id else 'costoverview/profile_id'

        wall_data = initialize_wall_data(profile_id, None, request_num_crews)
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
    authentication_classes = []

    @extend_schema(
        tags=['cost-overview'],
        operation_id='get_cost_overview_profile_id',
        summary='Get Profile Cost Overview',
        description='Retrieve the total cost for a specific wall profile.',
        parameters=open_api_parameters.cost_overview_profile_id_parameters + [open_api_parameters.num_crews_parameter],
        responses=open_api_resposnes.cost_overview_profile_id_responses
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
