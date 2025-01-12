from typing import Any, Dict

from django.http import JsonResponse
from django.views.defaults import page_not_found
from drf_spectacular.utils import extend_schema
from rest_framework.serializers import Serializer
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from the_wall_api.serializers import (
    ProfilesDaysSerializer, ProfilesOverviewDaySerializer, ProfilesOverviewSerializer,
    WallConfigFileDeleteSerializer, WallConfigFileUploadSerializer
)
from the_wall_api.utils import api_utils
from the_wall_api.utils.message_themes import (
    errors as error_messages, success as success_messages
)
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
            'accessed through the `profiles-days` and `profiles-overview` endpoints.'
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
            'details': success_messages.file_upload_details(config_id),
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


class ProfilesBaseView(APIView):
    throttle_classes = [UserRateThrottle]

    def process_profiles_request(
        self, request: Request, serializer_class: type[Serializer], profile_id=None, day=None,
        request_type: str | None = None
    ) -> tuple[Response | None, dict[str, Any]]:
        request_num_crews = api_utils.get_request_num_crews(request)
        config_id = request.query_params.get('config_id')
        num_crews = request.query_params.get('num_crews', 0)
        request_data = {'config_id': config_id, 'profile_id': profile_id, 'day': day, 'num_crews': num_crews}
        serializer = serializer_class(data=request_data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST), {}

        config_id = serializer.validated_data['config_id']          # type: ignore
        profile_id = serializer.validated_data.get('profile_id')    # type: ignore
        day = serializer.validated_data.get('day')                  # type: ignore
        num_crews = serializer.validated_data.get('num_crews', 0)   # type: ignore

        wall_data = initialize_wall_data(
            config_id=config_id, user=request.user, profile_id=profile_id,
            day=day, request_num_crews=request_num_crews, input_data=request.query_params
        )

        request_type = self.get_request_type(request_type, profile_id, day)
        fetch_wall_data(wall_data, num_crews, profile_id, request_type=request_type)

        if wall_data['error_response']:
            return wall_data['error_response'], {}
        if wall_data['info_response']:
            return wall_data['info_response'], {}

        return None, wall_data

    def get_request_type(
        self, request_type: str | None, profile_id: int | None, day: int | None
    ) -> str:
        if request_type:
            # profiles-days
            return request_type

        if profile_id and day:
            return 'single-profile-overview-day'
        elif day:
            return 'profiles-overview-day'

        return 'profiles-overview'

    def build_profiles_overview_response(
        self, wall_data: Dict[str, Any], profile_id: int | None, day: int | None
    ) -> Response:
        result_data = wall_data['cached_result']
        if not result_data:
            result_data = wall_data['simulation_result']

        if profile_id and day:
            cost = result_data['profile_day_cost']
            response_message = success_messages.profile_day_cost(profile_id, day)
        elif day:
            cost = result_data['profiles_overview_day_cost']
            response_message = success_messages.profiles_overview_day_cost(day)
        else:
            cost = result_data['wall_total_cost']
            response_message = success_messages.WALL_TOTAL_COST_RESPONSE

        response_data = {
            'day': day,
            'cost': success_messages.format_cost(cost),
            'profile_id': profile_id,
            'details': success_messages.profiles_overview_details(response_message, cost),
        }

        return Response(response_data, status=status.HTTP_200_OK)


class ProfilesDaysView(ProfilesBaseView):

    @extend_schema(
        tags=['Costs and Daily Ice Usage'],
        operation_id='get_profiles_days',
        summary='Daily Profile Construction Ice Amount',
        description='Retrieve the amount of ice used on a specific day for a given wall profile.',
        parameters=[open_api_parameters.num_crews_parameter, open_api_parameters.config_id_parameter],
        responses=open_api_responses.profiles_days_responses
    )
    def get(self, request: Request, profile_id: int, day: int) -> Response:
        response, wall_data = self.process_profiles_request(
            request, ProfilesDaysSerializer, profile_id, day, request_type='profiles-days'
        )
        if response:
            return response

        return self.build_profiles_days_response(wall_data, profile_id, day)

    def build_profiles_days_response(self, wall_data: Dict[str, Any], profile_id: int, day: int) -> Response:
        result_data = wall_data['cached_result']
        if not result_data:
            result_data = wall_data['simulation_result']
        profile_day_ice_amount = result_data['profile_day_ice_amount']
        response_data: Dict[str, Any] = {
            'profile_id': profile_id,
            'day': day,
        }

        if profile_day_ice_amount and isinstance(profile_day_ice_amount, int) and profile_day_ice_amount > 0:
            response_data['ice_amount'] = profile_day_ice_amount
            response_data['details'] = success_messages.profiles_days_details(
                profile_id, day, profile_day_ice_amount
            )
            return Response(response_data, status=status.HTTP_200_OK)

        response_data['details'] = error_messages.no_crew_worked_on_profile(profile_id, day)
        return Response(response_data, status=status.HTTP_404_NOT_FOUND)


class ProfilesOverviewView(ProfilesBaseView):

    @extend_schema(
        tags=['Costs and Daily Ice Amounts'],
        operation_id='get_profiles_overview',
        summary='Total Wall Construction Cost',
        description='Retrieve the total wall construction cost.',
        parameters=[open_api_parameters.num_crews_parameter, open_api_parameters.config_id_parameter],
        responses=open_api_responses.profiles_overview_responses
    )
    def get(self, request: Request) -> Response:
        profile_id = None
        day = None
        response, wall_data = self.process_profiles_request(
            request, ProfilesOverviewSerializer, profile_id=profile_id, day=day
        )
        if response:
            return response

        return self.build_profiles_overview_response(wall_data, profile_id=profile_id, day=day)


class ProfilesOverviewDayView(ProfilesBaseView):

    @extend_schema(
        tags=['Costs and Daily Ice Usage'],
        operation_id='get_profiles_overview_day',
        summary='Daily Wall Construction Cost',
        description='Retrieve the total construction cost for a specific day.',
        parameters=[open_api_parameters.num_crews_parameter, open_api_parameters.config_id_parameter],
        responses=open_api_responses.profiles_overview_responses
    )
    def get(self, request: Request, day: int) -> Response:
        profile_id = None
        response, wall_data = self.process_profiles_request(
            request, ProfilesOverviewDaySerializer, profile_id=profile_id, day=day
        )
        if response:
            return response

        return self.build_profiles_overview_response(wall_data, profile_id, day)


class SingleProfileOverviewDayView(ProfilesBaseView):

    @extend_schema(
        tags=['Costs and Daily Ice Usage'],
        operation_id='get_single_profile_overview_day',
        summary='Daily Profile Construction Cost',
        description='Retrieve the cost on a specific day for a given wall profile.',
        parameters=[open_api_parameters.num_crews_parameter, open_api_parameters.config_id_parameter],
        responses=open_api_responses.profiles_overview_responses
    )
    def get(self, request: Request, profile_id: int, day: int) -> Response:
        response, wall_data = self.process_profiles_request(
            request, ProfilesDaysSerializer, profile_id=profile_id, day=day
        )
        if response:
            return response

        return self.build_profiles_overview_response(wall_data, profile_id, day)


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
            'error': error_messages.ENDPOINT_NOT_FOUND,
            'error_details': error_messages.ENDPOINT_NOT_FOUND_DETAILS,
            'available_endpoints': available_endpoints,
        }
        return JsonResponse(response_data, status=404)
    else:
        return page_not_found(request, exception, template_name='404.html')
