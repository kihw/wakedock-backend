"""
Serializers package for WakeDock MVC architecture
"""

from .base_serializers import (
    BaseSerializer,
    BaseCreateSerializer,
    BaseUpdateSerializer,
    BaseResponseSerializer,
    PaginatedResponseSerializer
)
from .services_serializers import (
    ServiceCreateSerializer,
    ServiceUpdateSerializer,
    ServiceResponseSerializer,
    ServiceSummarySerializer,
    ServiceActionSerializer,
    ServiceBulkActionSerializer,
    ServiceFilterSerializer,
    ServiceStatsSerializer,
    ServiceLogsSerializer
)
from .auth_serializers import (
    LoginSerializer,
    RegisterSerializer,
    ProfileUpdateSerializer,
    PasswordChangeSerializer,
    PasswordResetRequestSerializer,
    PasswordResetSerializer,
    TokenRefreshSerializer,
    UserResponseSerializer,
    UserSummarySerializer,
    UserDetailSerializer,
    LoginResponseSerializer,
    RoleAssignmentSerializer,
    BulkUserActionSerializer,
    UserSearchSerializer,
    AuthStatsSerializer,
    SecurityMetricsSerializer
)

__all__ = [
    'BaseSerializer',
    'BaseCreateSerializer',
    'BaseUpdateSerializer',
    'BaseResponseSerializer',
    'PaginatedResponseSerializer',
    'ServiceCreateSerializer',
    'ServiceUpdateSerializer',
    'ServiceResponseSerializer',
    'ServiceSummarySerializer',
    'ServiceActionSerializer',
    'ServiceBulkActionSerializer',
    'ServiceFilterSerializer',
    'ServiceStatsSerializer',
    'ServiceLogsSerializer',
    'LoginSerializer',
    'RegisterSerializer',
    'ProfileUpdateSerializer',
    'PasswordChangeSerializer',
    'PasswordResetRequestSerializer',
    'PasswordResetSerializer',
    'TokenRefreshSerializer',
    'UserResponseSerializer',
    'UserSummarySerializer',
    'UserDetailSerializer',
    'LoginResponseSerializer',
    'RoleAssignmentSerializer',
    'BulkUserActionSerializer',
    'UserSearchSerializer',
    'AuthStatsSerializer',
    'SecurityMetricsSerializer'
]
