from typing import Any, Dict

from django.http import JsonResponse
from django.views.defaults import page_not_found
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from the_wall_api.serializers import (
    CostOverviewSerializer, DailyIceUsageSerializer,
    WallConfigFileDeleteSerializer, WallConfigFileUploadSerializer
)
from the_wall_api.utils import api_utils
from the_wall_api.utils.open_api_schema_utils import (
    open_api_parameters, open_api_responses, open_api_schemas
)
from the_wall_api.utils.storage_utils import (
    fetch_user_wall_config_files, fetch_wall_data,
    manage_wall_config_file_delete, manage_wall_config_file_upload
)
from the_wall_api.wall_construction import initialize_wall_data


class WallConfigFileUploadView(APIView):
    serializer_class = WallConfigFileUploadSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'wallconfig-files-management'

    @extend_schema(
        tags=['File Management'],
        summary='Upload Wall Configuration File',
        description=(
            'Allows users to upload wall configuration files, which are '
            'parsed and stored as structured data in the database. \n\nThe processed data can be '
            'accessed through the `daily-ice-usage`, `cost-overview`, and `cost-overview-profile` endpoints.'
            '<br><br>'
            '*<b><i>Swagger UI-only:</i></b> \n\n'
            '<i>If a file upload fails due to validation errors,</i> \n\n'
            '<i>and the file is subsequently modified to meet the validation requirements,</i> \n\n'
            '<i>the "Try it out" functionality must be reset before attempting a second upload.</i>'
        ),
        request=open_api_schemas.wallconfig_file_upload_schema,
        responses=open_api_responses.wallconfig_file_upload_responses
    )
    def post(self, request):
        serializer = self.serializer_class(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        config_id = serializer.validated_data['config_id']                      # type: ignore
        wall_config_file_data = serializer.context['wall_config_file_data']     # type: ignore

        wall_data = initialize_wall_data(
            source='wallconfig_file_view', request_type='wallconfig-files/upload', user=request.user,
            wall_config_file_data=wall_config_file_data, config_id=config_id, input_data=request.data
        )
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
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        tags=['File Management'],
        summary='List Wall Configuration Files',
        description='Retrieve a list of wall configuration files uploaded by the user.',
        responses=open_api_responses.wallconfig_file_list_responses
    )
    def get(self, request):
        wall_data = initialize_wall_data(
            source='wallconfig_file_view', request_type='wallconfig-files/list',
            user=request.user
        )
        config_id_list = fetch_user_wall_config_files(wall_data)
        if wall_data['error_response']:
            return wall_data['error_response']

        response_data = {
            'config_id_list': config_id_list
        }
        return Response(response_data, status=status.HTTP_200_OK)


class WallConfigFileDeleteView(APIView):
    serializer_class = WallConfigFileDeleteSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'wallconfig-files-management'

    @extend_schema(
        tags=['File Management'],
        summary='Delete Wall Configuration File',
        description='Delete a wall configuration file uploaded by the user.',
        parameters=[open_api_parameters.file_delete_config_id_list_parameter],
        responses=open_api_responses.wallconfig_file_delete_responses
    )
    def delete(self, request):
        serializer = WallConfigFileDeleteSerializer(
            data=request.query_params
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        request_config_id_list = serializer.validated_data.get('config_id_list', [])    # type: ignore

        wall_data = initialize_wall_data(
            source='wallconfig_file_view', request_type='wallconfig-files/delete', user=request.user,
            request_config_id_list=request_config_id_list
        )
        manage_wall_config_file_delete(wall_data)
        if wall_data['error_response']:
            return wall_data['error_response']

        return Response(status=status.HTTP_204_NO_CONTENT)


class DailyIceUsageView(APIView):
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        tags=['Costs and Daily Ice Usage '],
        summary='Get Daily Ice Usage',
        description='Retrieve the amount of ice used on a specific day for a given wall profile.',
        parameters=open_api_parameters.daily_ice_usage_parameters +
        [open_api_parameters.num_crews_parameter, open_api_parameters.config_id_parameter],
        responses=open_api_responses.daily_ice_usage_responses
    )
    def get(self, request: Request, profile_id: int, day: int) -> Response:
        request_num_crews = api_utils.get_request_num_crews(request)
        config_id = request.query_params.get('config_id')
        num_crews = request.query_params.get('num_crews', 0)
        serializer = DailyIceUsageSerializer(
            data={'config_id': config_id, 'profile_id': profile_id, 'day': day, 'num_crews': num_crews}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        config_id = serializer.validated_data['config_id']      # type: ignore
        profile_id = serializer.validated_data['profile_id']    # type: ignore
        day = serializer.validated_data['day']                  # type: ignore
        num_crews = serializer.validated_data['num_crews']      # type: ignore

        wall_data = initialize_wall_data(
            config_id=config_id, user=request.user, profile_id=profile_id,
            day=day, request_num_crews=request_num_crews, input_data=request.query_params
        )
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
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        tags=['Costs and Daily Ice Usage '],
        operation_id='get_cost_overview',
        summary='Get Cost Overview',
        description='Retrieve the total wall construction cost.',
        parameters=[open_api_parameters.config_id_parameter],
        responses=open_api_responses.cost_overview_responses
    )
    def get(self, request: Request, profile_id: int | None = None) -> Response:
        config_id = request.query_params.get('config_id')
        request_data = {'config_id': config_id, 'profile_id': profile_id}
        cost_serializer = CostOverviewSerializer(data=request_data)
        if not cost_serializer.is_valid():
            return Response(cost_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        config_id = cost_serializer.validated_data['config_id']     # type: ignore
        profile_id = cost_serializer.validated_data['profile_id']   # type: ignore

        request_type = 'costoverview' if not profile_id else 'costoverview/profile_id'

        wall_data = initialize_wall_data(
            config_id=config_id, user=request.user,
            profile_id=profile_id, day=None, input_data=request.query_params
        )
        fetch_wall_data(wall_data, profile_id=profile_id, request_type=request_type)
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
    throttle_classes = [UserRateThrottle]

    @extend_schema(
        tags=['Costs and Daily Ice Usage '],
        operation_id='get_cost_overview_profile_id',
        summary='Get Profile Cost Overview',
        description='Retrieve the total cost for a specific wall profile.',
        parameters=open_api_parameters.cost_overview_profile_id_parameters +
        [open_api_parameters.config_id_parameter],
        responses=open_api_responses.cost_overview_profile_id_responses
    )
    def get(self, request: Request, profile_id: int | None = None) -> Response:
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
