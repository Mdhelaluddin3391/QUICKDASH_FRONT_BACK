# apps/accounts/permissions.py
from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request,
        if request.method in permissions.SAFE_METHODS:
            return True

        # 1. Direct User Model
        if hasattr(obj, 'phone') and hasattr(obj, 'email') and obj == request.user:
             return True

        # 2. Linked User Field (Order, etc.)
        if hasattr(obj, 'user') and obj.user == request.user:
            return True
            
        # 3. Linked Rider Profile
        if hasattr(obj, 'rider') and obj.rider.user == request.user:
            return True
            
        # 4. Linked Customer Profile
        if hasattr(obj, 'customer') and obj.customer.user == request.user:
            return True

        return False

class IsCustomer(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.roles.filter(role='customer').exists()
        )

class IsRider(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.roles.filter(role='rider').exists()
        )

class IsWarehouseManager(permissions.BasePermission):
    def has_permission(self, request, view):
        return bool(
            request.user and 
            request.user.is_authenticated and 
            request.user.roles.filter(role='employee').exists()
        )

    def has_object_permission(self, request, view, obj):
        # Strict warehouse scoping if object belongs to a warehouse
        # Assuming EmployeeProfile links to Warehouse
        if hasattr(request.user, 'employee_profile') and hasattr(obj, 'warehouse'):
            return obj.warehouse == request.user.employee_profile.warehouse
        return True # Default to True if object isn't warehouse-scoped (or implement stricter logic)