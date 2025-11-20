"""
Utility functions for error handling
"""
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.db import connection
import logging

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler to ensure all errors return JSON,
    even database connection errors.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)
    
    # If REST framework handled it, return JSON response
    if response is not None:
        return response
    
    # If it's a database error or other unhandled exception,
    # return a JSON error response instead of HTML
    logger.exception("Unhandled exception occurred")
    
    # Check if request is for API endpoint
    request = context.get('request')
    if request and request.path.startswith('/api/'):
        # Check database connection
        try:
            connection.ensure_connection()
        except Exception as db_error:
            return Response(
                {
                    "error": "Database connection error",
                    "detail": str(db_error) if str(db_error) else "Unable to connect to database",
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Generic error response
        return Response(
            {
                "error": "Internal server error",
                "detail": str(exc) if str(exc) else "An unexpected error occurred",
            },
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # For non-API endpoints, return None to use Django's default handler
    return None

