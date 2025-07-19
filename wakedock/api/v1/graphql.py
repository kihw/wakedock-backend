"""
GraphQL API endpoint for WakeDock
"""

from fastapi import APIRouter, Depends, HTTPException
from strawberry.fastapi import GraphQLRouter
from strawberry.subscriptions import GRAPHQL_TRANSPORT_WS_PROTOCOL, GRAPHQL_WS_PROTOCOL
import strawberry

from wakedock.graphql.schema import schema
from wakedock.core.auth import get_current_user
from wakedock.core.rbac_service import RBACService
from wakedock.database.models import User

# Create GraphQL router
graphql_router = GraphQLRouter(
    schema,
    subscription_protocols=[
        GRAPHQL_TRANSPORT_WS_PROTOCOL,
        GRAPHQL_WS_PROTOCOL,
    ],
    path="/graphql",
    include_in_schema=True,
)

# Create API router
router = APIRouter()

# Add GraphQL endpoint with authentication
@router.api_route("/graphql", methods=["GET", "POST"])
async def graphql_endpoint(
    request,
    user: User = Depends(get_current_user),
    rbac: RBACService = Depends(RBACService.get_instance)
):
    """GraphQL endpoint with authentication and authorization"""
    
    # Check if user has GraphQL access permission
    if not rbac.check_permission(user, "graphql", "access"):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions for GraphQL access"
        )
    
    # Add user context to GraphQL request
    context = {
        "user": user,
        "rbac": rbac,
        "request": request,
    }
    
    return await graphql_router.handle_request(request, context)


# WebSocket endpoint for subscriptions
@router.websocket("/graphql")
async def graphql_websocket_endpoint(
    websocket,
    user: User = Depends(get_current_user),
    rbac: RBACService = Depends(RBACService.get_instance)
):
    """GraphQL WebSocket endpoint for subscriptions"""
    
    # Check if user has GraphQL subscription permission
    if not rbac.check_permission(user, "graphql", "subscribe"):
        await websocket.close(code=4003, reason="Insufficient permissions")
        return
    
    # Add user context to WebSocket connection
    context = {
        "user": user,
        "rbac": rbac,
        "websocket": websocket,
    }
    
    await graphql_router.handle_websocket(websocket, context)


# GraphQL Playground endpoint (development only)
@router.get("/graphql/playground")
async def graphql_playground():
    """GraphQL Playground for development"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>GraphQL Playground</title>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <link
            rel="stylesheet"
            href="//cdn.jsdelivr.net/npm/graphql-playground-react/build/static/css/index.css"
        />
        <link rel="shortcut icon" href="//cdn.jsdelivr.net/npm/graphql-playground-react/build/favicon.png" />
        <script src="//cdn.jsdelivr.net/npm/graphql-playground-react/build/static/js/middleware.js"></script>
    </head>
    <body>
        <div id="root">
            <style>
                body {
                    background-color: rgb(23, 42, 58);
                    font-family: Open Sans, sans-serif;
                    height: 90vh;
                }
                #root {
                    height: 100%;
                    width: 100%;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                .loading {
                    font-size: 32px;
                    font-weight: 200;
                    color: rgba(255, 255, 255, .6);
                    margin-left: 20px;
                }
                img {
                    width: 78px;
                    height: 78px;
                }
                .title {
                    font-weight: 400;
                }
            </style>
            <img src="//cdn.jsdelivr.net/npm/graphql-playground-react/build/logo.png" alt="" />
            <div class="loading"> Loading
                <span class="title">GraphQL Playground</span>
            </div>
        </div>
        <script>
            window.addEventListener('load', function (event) {
                GraphQLPlayground.init(document.getElementById('root'), {
                    endpoint: '/api/v1/graphql',
                    subscriptionsEndpoint: '/api/v1/graphql',
                    settings: {
                        'editor.theme': 'dark',
                        'editor.fontSize': 14,
                        'editor.fontFamily': 'Consolas, Monaco, "Courier New", monospace',
                        'request.credentials': 'same-origin',
                    },
                    tabs: [
                        {
                            endpoint: '/api/v1/graphql',
                            query: `# WakeDock GraphQL API
# Welcome to GraphQL Playground!
# 
# Example queries:

# Get all containers
query GetContainers {
  containers {
    id
    name
    image
    status
    created
    ports {
      containerPort
      hostPort
      protocol
    }
  }
}

# Get system information
query GetSystemInfo {
  systemInfo {
    version
    dockerVersion
    platform
    cpuCount
    memoryTotal
    memoryUsagePercent
    diskUsagePercent
    containersRunning
    containersStopped
  }
}

# Subscribe to container events
subscription ContainerEvents {
  containerEvents {
    id
    name
    status
    created
  }
}`,
                        },
                    ],
                })
            })
        </script>
    </body>
    </html>
    """


# Add GraphQL router to main router
router.include_router(graphql_router, prefix="")

# Export the router
__all__ = ["router"]