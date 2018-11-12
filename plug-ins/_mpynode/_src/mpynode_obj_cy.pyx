import maya.api.OpenMaya as om

from maya.api.OpenMaya import MAngle, MColor, MColorArray, MEulerRotation, MFnNurbsCurve, MMatrix, MMatrixArray, MPoint, MPointArray, MQuaternion, MTime, MTimeArray, MVector, MVectorArray


cpdef _getFloatInput(node, data_block, plug, is_array=False):
    """
    Generic method fot getting the plugs input value using the given MDataHandle function name (get_func_name).
    Returns a value or tuple of values depending on the is_array arg.
    """
    
    cdef Py_ssize_t num_elements
    cdef unsigned i
    cdef double val
    cdef list values = []
    
    if not is_array:
        in_handle = data_block.inputValue(plug)
        return in_handle.asDouble()
        
    else:
        in_handles = data_block.inputArrayValue(plug)
        num_elements = len(in_handles)

        if num_elements > 0:
        
            for i in range(num_elements):

                in_handle = in_handles.inputValue()
                val = in_handle.asDouble()
                values.append(val)

                if i != (num_elements - 1):
                    in_handles.next()

            return values

    return None
    
    
cpdef _getIntInput(node, data_block, plug, is_array=False):
    """
    Generic method fot getting the plugs input value using the given MDataHandle function name (get_func_name).
    Returns a value or tuple of values depending on the is_array arg.
    """
    
    cdef Py_ssize_t num_elements
    cdef unsigned i
    cdef int val
    cdef list values = []
    
    if not is_array:
        in_handle = data_block.inputValue(plug)
        return in_handle.asInt()
        
    else:
        in_handles = data_block.inputArrayValue(plug)
        num_elements = len(in_handles)

        if num_elements > 0:
        
            for i in range(num_elements):

                in_handle = in_handles.inputValue()
                val = in_handle.asInt()
                values.append(val)

                if i != (num_elements - 1):
                    in_handles.next()

            return values

    return None
    
    
cpdef _getStringInput(node, data_block, plug, is_array=False):
    """
    Generic method fot getting the plugs input value using the given MDataHandle function name (get_func_name).
    Returns a value or tuple of values depending on the is_array arg.
    """
    
    cdef Py_ssize_t num_elements
    cdef unsigned i
    cdef int val
    cdef list values = []
    
    if not is_array:
        in_handle = data_block.inputValue(plug)
        return in_handle.asString()
        
    else:
        in_handles = data_block.inputArrayValue(plug)
        num_elements = len(in_handles)

        if num_elements > 0:
        
            for i in range(num_elements):

                in_handle = in_handles.inputValue()
                val = in_handle.asString()
                values.append(val)

                if i != (num_elements - 1):
                    in_handles.next()

            return values

    return None
    
    
cpdef _getVectorInput(node, data_block, plug, is_array=False):
    """
    Generic method fot getting the plugs input value using the given MDataHandle function name (get_func_name).
    Returns a value or tuple of values depending on the is_array arg.
    """
    
    cdef Py_ssize_t num_elements
    cdef unsigned i
    
    if not is_array:
        in_handle = data_block.inputValue(plug)
        return in_handle.asVector()
        
    else:
        in_handles = data_block.inputArrayValue(plug)
        num_elements = len(in_handles)

        if num_elements > 0:
        
            values = MVectorArray()
        
            for i in range(num_elements):
                in_handle = in_handles.inputValue()
                values.append(in_handle.asVector())

                if i != (num_elements - 1):
                    in_handles.next()

            return values

    return None