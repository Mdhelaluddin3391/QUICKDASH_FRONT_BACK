from rest_framework import permissions

class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Object-level permission to only allow owners of an object to edit it.
    """
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True

        if hasattr(obj, 'phone') and hasattr(obj, 'email') and obj == request.user:
             return True

        if hasattr(obj, 'user') and obj.user == request.user:
            return True
            
        if hasattr(obj, 'rider') and obj.rider.user == request.user:
            return True
            
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
        
        if hasattr(request.user, 'employee_profile') and hasattr(obj, 'warehouse'):
            return obj.warehouse == request.user.employee_profile.warehouse
        return True 