"""
This module is for adding functionality to existing Maya API classes
"""

import maya.api.OpenMaya as om


class MAngle(om.MAngle):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """

    def __init__(self, *args):

        super(MAngle, self).__init__(*args)


    def __reduce__(self):

        return (MAngle, (self.asRadians(), MAngle.kRadians))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __repr__(self):

        return super(MAngle, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.")


class MColor(om.MColor):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """

    def __init__(self, clr=None, model=om.MColor.kRGB, dataType=om.MColor.kFloat):

        self._model = model
        self._data_type = dataType

        if clr:
            super(MColor, self).__init__(clr, model=model, dataType=dataType)

        else:
            super(MColor, self).__init__()


    def __reduce__(self):

        return (MColor, ((self.r, self.g, self.b, self.a), self._model, self._data_type))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __add__(self, y):

        return MColor(super(MColor, self).__add__(y))


    def __radd__(self, y):

        return MColor(super(MColor, self).__radd__(y))


    def __iadd__(self, y):

        return MColor(super(MColor, self).__iadd__(y))


    def __mul__(self, y):

        return  MColor(super(MColor, self).__mul__(y))


    def __rmul__(self, y):

        return  MColor(super(MColor, self).__rmul__(y))


    def __imul__(self, y):

        return  MColor(super(MColor, self).__imul__(y))


    def __div__(self, y):

        return MColor(super(MVector, self).__div__(y))


    def __idiv__(self, y):

        return MColor(super(MVector, self).__idiv__(y))


    def __rdiv__(self, y):

        return MColor(super(MVector, self).__rdiv__(y))


    def __str__(self):

        return str((self.r, self.g, self.b, self.a))


    def __repr__(self):

        return super(MColor, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.")


    def setColor(self, clr, model=om.MColor.kRGB, dataType=om.MColor.kFloat):
        """
        Override of the base class version to add functionality
        """

        self._model = model
        self._data_type = dataType

        super(MColor, self).setColor(clr, model=model, dataType=dataType)


    def getColorModel(self):
        """
        Returns the color model used by this MColor object

        *RETURNS*	*int* representing the color model type such as MColor.kRGB
        """

        return self._model


    def getDataType(self):
        """
        Returns the color data type used by this MColor object

        *RETURNS*	*int* representing the color data type such as MColor.kFloat
        """

        return self._data_type


class MColorArray(om.MColorArray):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args):

        super(MColorArray, self).__init__(*args)


    def __reduce__(self):

        return (MColorArray, (tuple([tuple(clr) for clr in self]),))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __getitem__(self, i):

        return MColor(super(MColorArray, self).__getitem__(i))


    def __getslice__(self, i, j):

        return MColorArray(super(MVectorArray, self).__getslice__(i, j))


    def __repr__(self):

        return super(MColorArray, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.")


    def __str__(self):

        return super(MColorArray, self).__str__().replace("maya.api.OpenMaya.", "MPyNode.")


class MEulerRotation(om.MEulerRotation):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args, **kargs):

        super(MEulerRotation, self).__init__(*args, **kargs)


    def __reduce__(self):

        return (MEulerRotation, (self.x, self.y, self.z, self.order))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __str__(self):

        return str((self.x, self.y, self.z))


    def __repr__(self):

        return super(MEulerRotation, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.")


    def __add__(self, y):

        return MEulerRotation(super(MEulerRotation, self).__add__(y))


    def __radd__(self, y):

        return MEulerRotation(super(MEulerRotation, self).__radd__(y))


    def __iadd__(self, y):

        return MEulerRotation(super(MEulerRotation, self).__iadd__(y))


    def __sub__(self, y):

        return MEulerRotation(super(MEulerRotation, self).__sub__(y))


    def __rsub__(self, y):

        return MEulerRotation(super(MEulerRotation, self).__rsub__(y))


    def __isub__(self, y):

        return MEulerRotation(super(MEulerRotation, self).__isub__(y))


    def __mul__(self, y):

        return MEulerRotation(super(MEulerRotation, self).__mul__(y))


    def __rmul__(self, y):

        return MEulerRotation(super(MEulerRotation, self).__rmul__(y))


    def __imul__(self, y):

        return MEulerRotation(super(MEulerRotation, self).__imul__(y))


    def alternateSolution(self):

        return MEulerRotation(super(MEulerRotation, self).alternateSolution())


    def asMatrix(self):

        return MMatrix(super(MEulerRotation, self).asMatrix())


    def asQuaternion(self):

        return MQuaternion(super(MEulerRotation, self).asQuaternion())


    def asVector(self):

        return MVector(super(MEulerRotation, self).asVector())


    def bound(self):

        return MEulerRotation(super(MEulerRotation, self).bound())


    def closestCut(self, target):

        return MEulerRotation(super(MEulerRotation, self).closestCut(target))


    def closestSolution(self, target):

        return MEulerRotation(super(MEulerRotation, self).closestSolution(target))


    @staticmethod
    def computeAlternateSolution(rot):

        return MEulerRotation(om.MEulerRotation.computeAlternateSolution(rot))


    @staticmethod
    def computeBound(rot):

        return MEulerRotation(om.MEulerRotation.computeBound(rot))


    @staticmethod
    def computeClosestCut(src, target):

        return MEulerRotation(om.MEulerRotation.computeClosestCut(src, target))


    @staticmethod
    def computeClosestSolution(src, target):

        return MEulerRotation(om.MEulerRotation.computeClosestSolution(src, target))


    @staticmethod
    def decompose(matrix, order):

        return MEulerRotation(om.MEulerRotation.decompose(matrix, order))


    def inverse(self):

        return MEulerRotation(super(MEulerRotation, self).inverse())


    def reorder(self, order):

        return MEulerRotation(super(MEulerRotation, self).reorder(order))


class MFnMesh(om.MFnMesh):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args, **kargs):

        super(MFnMesh, self).__init__(*args, **kargs)


    def getPoints(self, space=om.MSpace.kObject):

        return MPointArray(super(MFnMesh, self).getPoints(space))


class MFnNurbsCurve(om.MFnNurbsCurve):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args, **kargs):

        super(MFnNurbsCurve, self).__init__(*args, **kargs)


    def closestPoint(self, test_pnt, guess=None, tolerance=om.MFnNurbsCurve.kPointTolerance, space=om.MSpace.kObject):

        pnt, param = super(MFnNurbsCurve, self).closestPoint(test_pnt, guess, tolerance, space)

        return MPoint(pnt), param


    def cvPosition(self, index, space=om.MSpace.kObject):

        return MPoint(super(MFnNurbsCurve, self).cvPosition(index, space))


    def cvPositions(self, space=om.MSpace.kObject):

        return MPointArray(super(MFnNurbsCurve, self).cvPositions(space))


    def getDerivativesAtParam(self, param, space=om.MSpace.kObject, dUU=False):

        result = super(MFnNurbsCurve, self).getDerivativesAtParam(param, space=space, dUU=dUU)

        if len(result) < 3:
            return MPoint(result[0]), MVector(result[1])

        else:
            return MPoint(result[0]), MVector(result[1]), MVector(result[2])


    def getPointAtParam(self, param, space=om.MSpace.kObject):

        return MPoint(super(MFnNurbsCurve, self).getPointAtParam(param, space))


    def normal(self, param, space=om.MSpace.kObject):

        return MVector(super(MFnNurbsCurve, self).normal(param, space))


    def tangent(self, param, space=om.MSpace.kObject):

        return MVector(super(MFnNurbsCurve, self).tangent(param, space))



class MMatrix(om.MMatrix):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args):

        super(MMatrix, self).__init__(*args)


    def __reduce__(self):

        return (MMatrix, (tuple(self),))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __add__(self, y):

        return MMatrix(super(MMatrix, self).__add__(y))


    def __radd__(self, y):

        return MMatrix(super(MMatrix, self).__radd__(y))


    def __iadd__(self, y):

        return MMatrix(super(MMatrix, self).__iadd__(y))


    def __sub__(self, y):

        return MMatrix(super(MMatrix, self).__sub__(y))


    def __rsub__(self, y):

        return MMatrix(super(MMatrix, self).__rsub__(y))


    def __isub__(self, y):

        return MMatrix(super(MMatrix, self).__isub__(y))


    def __mul__(self, y):

        result = super(MMatrix, self).__mul__(y)

        if result is NotImplemented:
            return NotImplemented

        return MMatrix(result)


    def __rmul__(self, y):

        return MMatrix(super(MMatrix, self).__rmul__(y))


    def __imul__(self, y):

        return MMatrix(super(MMatrix, self).__imul__(y))


    def adjoint(self):
        """
        Returns a new matrix containing this matrix's adjoint.
        """

        return MMatrix(super(MMatrix, self).adjoint())


    def homogenize(self):
        """
        Returns a new matrix containing the homogenized version of this matrix.
        """

        return MMatrix(super(MMatrix, self).homogenize())


    def inverse(self):
        """
        Returns a new matrix containing this matrix's inverse.
        """

        return MMatrix(super(MMatrix, self).inverse())


    def transpose(self):
        """
        Returns a new matrix containing this matrix's inverse.
        """

        return MMatrix(super(MMatrix, self).transpose())


class MMatrixArray(om.MMatrixArray):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args):

        super(MMatrixArray, self).__init__(*args)


    def __reduce__(self):

        return (MMatrixArray, (tuple([tuple(mat) for mat in self]),))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __getitem__(self, i):

        return MMatrix(super(MMatrixArray, self).__getitem__(i))


    def __getslice__(self, i, j):

        return MMatrixArray(super(MMatrixArray, self).__getslice__(i, j))


    def __repr__(self):

        return super(MMatrixArray, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.")


    def __str__(self):

        return super(MMatrixArray, self).__str__().replace("maya.api.OpenMaya.", "MPyNode.")


class MPoint(om.MPoint):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args):

        super(MPoint, self).__init__(*args)


    def __reduce__(self):

        return (MPoint, (self.x, self.y, self.z, self.w))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __add__(self, y):

        return MPoint(super(MPoint, self).__add__(y))


    def __radd__(self, y):

        return MPoint(super(MPoint, self).__radd__(y))


    def __iadd__(self, y):

        return MPoint(super(MPoint, self).__iadd__(y))


    def __mul__(self, y):

        return  MPoint(super(MPoint, self).__mul__(y))


    def __rmul__(self, y):

        return  MPoint(super(MPoint, self).__rmul__(y))


    def __imul__(self, y):

        return  MPoint(super(MPoint, self).__imul__(y))


    def __div__(self, y):

        return MPoint(super(MPoint, self).__div__(y))


    def __rdiv__(self, y):

        return MPoint(super(MPoint, self).__rdiv__(y))


    def __sub__(self, y):

        diff = super(MPoint, self).__sub__(y)

        if type(diff) == om.MVector:
            return MVector(diff)

        return MPoint(diff)


    def __rsub__(self, y):

        diff = super(MPoint, self).__rsub__(y)

        if type(diff) == om.MVector:
            return MVector(diff)

        return MPoint(diff)


    def __isub__(self, y):
        """
        In-place subtract
        """

        return MPoint(super(MPoint, self).__isub__(y))


    def __str__(self):

        return str((self.x, self.y, self.z, self.w))


    def __repr__(self):

        return super(MPoint, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.")


class MPointArray(om.MPointArray):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args):

        super(MPointArray, self).__init__(*args)


    def __reduce__(self):

        return (MPointArray, (tuple([tuple(pnt) for pnt in self]),))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __add__(self, y):

        ##---some reason calling __add__ directly on the parent class causes a crash (WTF?)----##
        return MPointArray(om.MPointArray(self) + y)


    def __iadd__(self, y):

        return MPointArray(super(MVectorArray, self).__iadd__(y))


    def __getitem__(self, i):

        return MPoint(super(MPointArray, self).__getitem__(i))


    def __getslice__(self, i, j):

        return MPointArray(super(MPointArray, self).__getslice__(i, j))


    def __repr__(self):

        return super(MPointArray, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.")


    def __str__(self):

        return super(MPointArray, self).__str__().replace("maya.api.OpenMaya.", "MPyNode.")


class MQuaternion(om.MQuaternion):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args):

        super(MQuaternion, self).__init__(*args)


    def __reduce__(self):

        return (MQuaternion, (self.x, self.y, self.z, self.w))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __str__(self):

        return str((self.x, self.y, self.z, self.w))


    def __repr__(self):

        return super(MQuaternion, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.")


    def __add__(self, y):

        return MQuaternion(super(MQuaternion, self).__add__(y))


    def __radd__(self, y):

        return MQuaternion(super(MQuaternion, self).__radd__(y))


    def __sub__(self, y):

        return MQuaternion(super(MQuaternion, self).__sub__(y))


    def __rsub__(self, y):

        return MQuaternion(super(MQuaternion, self).__rsub__(y))


    def __mul__(self, y):

        return MQuaternion(super(MQuaternion, self).__mul__(y))


    def __rmul__(self, y):

        return MQuaternion(super(MQuaternion, self).__rmul__(y))


    def __imul__(self, y):

        return MQuaternion(super(MQuaternion, self).__imul__(y))


    def __neg__(self):
        """
        Component-by-component negation
        """

        return MQuaternion(super(MQuaternion, self).__neg__())


    def asAxisAngle(self):
        """
        Returns the rotation as a tuple containing an axis vector and an angle in radians about that axis.
        """

        vect, angle = super(MQuaternion, self).asAxisAngle()

        return MVector(vect), angle


    def asEulerRotation(self):
        """
        Returns the rotation as an equivalent MEulerRotation.
        """

        return MEulerRotation(super(MQuaternion, self).asEulerRotation())


    def asMatrix(self):
        """
        Returns the rotation as an equivalent rotation matrix.
        """

        return MMatrix(super(MQuaternion, self).asMatrix())


    def conjugate(self):
        """
        Returns the conjugate of this quaternion (i.e. x, y and z components negated).
        """

        return MQuaternion(super(MQuaternion, self).conjugate())


    def exp(self):
        """
        Returns a new quaternion containing the exponent of this one.
        """

        return MQuaternion(super(MQuaternion, self).exp())


    def inverse(self):
        """
        Returns a new quaternion containing the inverse of this one.
        """

        return MQuaternion(super(MQuaternion, self).inverse())


    def log(self):
        """
        Returns a new quaternion containing the log of this one.
        """

        return MQuaternion(super(MQuaternion, self).log())


    def normal(self):
        """
        Returns a new quaternion containing the normalized version of this one (i.e. scaled to unit length).
        """

        return MQuaternion(super(MQuaternion, self).normal())


    @staticmethod
    def slerp(p, q, t, spin):
        """
        Spherical interpolation of unit quaternions. Returns a quaternion along the shortest path (in quaternion space)
        between p and q, at interpolation value t. Thus a value of 0.0 will return p while a value of 1.0 will return q.
        spin gives the number of complete rotations about the axis which must occur when going from p to q.
        """

        return MQuaternion(om.MQuaternion.slerp(p, q, t, spin))


    @staticmethod
    def squad(p, a, b, q, t, spin=0):
        """
        Interpolation along a cubic curve segment in quaternion space. Returns a quaternion along the cubic curve
        segment which interpolates p and q, at interpolation value t. Thus a value of 0.0 will return p while a value
        of 1.0 will return q. The curve is C1 continuous with a and b as intermediate points. spins gives the number of
        complete rotations about the axis which must occur when going from p to q.
        """

        return MQuaternion(om.MQuaternion.squad(p, a, b, q, t, spin))


    @staticmethod
    def squadPt(q0, q1, q2):
        """
        Returns a new quaternion representing an intermediate point (in quaternion space) which when used with squad()
        will produce a C1 continuous spline.
        """

        return MQuaternion(om.MQuaternion.squadPt(q0, q1, q2))


class MTime(om.MTime):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """

    def __init__(self, *args, **kargs):

        super(MTime, self).__init__(*args, **kargs)


    def __reduce__(self):

        return (MTime, (self.value, self.unit))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __str__(self):

        return super(MTime, self).__str__()


    def __repr__(self):

        return super(MTime, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.")


class MTimeArray(om.MTimeArray):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args):

        in_times = None

        if args:
            ##---init from anoth MtimeArray---##
            if type(args[0]) in  (list, tuple):
                in_times = args[0]
                args = ()

        super(MTimeArray, self).__init__(*args)

        if in_times:
            for time_args in in_times:

                if isinstance(time_args, MTime):
                    self.append(MTime(time_args))
                else:
                    self.append(MTime(*time_args))


    def __reduce__(self):

        return (MTimeArray, (tuple([(time.value, time.unit) for time in self]),))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __getitem__(self, i):

        return MTime(super(MTimeArray, self).__getitem__(i))


    def __getslice__(self, i, j):

        return MTimeArray(super(MTimeArray, self).__getslice__(i, j))


    def __str__(self):

        return super(MTimeArray, self).__str__().replace("maya.api.OpenMaya.", "MPyNode.")


    def __repr__(self):

        return super(MTimeArray, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.")


class MVector(om.MVector):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """

    def __init__(self, *args):

        super(MVector, self).__init__(*args)


    def __reduce__(self):

        return (MVector, (self.x, self.y, self.z))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __add__(self, y):

        return MVector(super(MVector, self).__add__(y))


    def __radd__(self, y):

        return MVector(super(MVector, self).__radd__(y))


    def __iadd__(self, y):

        return MVector(super(MVector, self).__iadd__(y))


    def __sub__(self, y):

        return MVector(super(MVector, self).__sub__(y))


    def __rsub__(self, y):

        return MVector(super(MVector, self).__rsub__(y))


    def __isub__(self, y):
        """
        In-place subtract
        """

        return MVector(super(MVector, self).__isub__(y))


    def __xor__(self, y):
        """
        Cross product
        """

        return MVector(super(MVector, self).__xor__(y))


    def __rxor__(self, y):
        """
        Reverse cross product
        """

        return MVector(super(MVector, self).__rxor__(y))


    def __mul__(self, y):

        result = super(MVector, self).__mul__(y)

        if type(result) == om.MVector:
            return MVector(result)

        return result


    def __rmul__(self, y):

        result = super(MVector, self).__rmul__(y)

        if type(result) == om.MVector:
            return MVector(result)

        return result


    def __imul__(self, y):

        result = super(MVector, self).__imul__(y)

        if type(result) == om.MVector:
            return MVector(result)

        return result


    def __div__(self, y):

        return MVector(super(MVector, self).__div__(y))


    def __idiv__(self, y):

        return MVector(super(MVector, self).__idiv__(y))


    def __rdiv__(self, y):

        return MVector(super(MVector, self).__rdiv__(y))


    def __neg__(self):
        """
        New vector which is the negative if the given vector.
        """

        return MVector(super(MVector, self).__neg__())


    def __str__(self):

        return str((self.x, self.y, self.z))


    def __repr__(self):

        return super(MVector, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.")


    def normal(self):
        """
        Returns a new vector containing the normalized version of this one.

        **RETURNS** 	*MVector*

        >>> new_v = v.normal()

        """

        return MVector(super(MVector, self).normal())


    def normalize(self):
        """
        Normalizes this vector in-place and returns a new reference to it.

        **RETURNS** 	*MVector*

        >>> v.normalize()

        """

        return MVector(super(MVector, self).normalize())


    def rotateBy(self, *args):
        """
        Returns the vector resulting from rotating this one by the given amount.

        **args**		single *MQuaternion* or *MEulerRotation*, or an axis identifier constant and a *float* angle

        **RETURNS** 	*MVector*

        >>> ##---rotate by MQuaternion or MEulerRotation---##
        >>> new_v = v.rotateBy(rot)
        >>>
        >>> ##---rotate by angle radians about the specified axis---##
        >>> new_v = v.rotateBy(MVector.kXaxis, 5.0)

        """

        return MVector(super(MVector, self).rotateBy(*args))


    def rotateTo(self, target):
        """
        Returns the quaternion which will rotate this vector into another.

        **target**		*MVector*

        **RETURNS** 	*MQuaternion*

        >>> q = v.rotateTo(MVector(1.0, 0.0, 0.0))

        """

        return MQuaternion(super(MVector, self).rotateTo(target))


    def transformAsNormal(self, matrix):
        """
        Returns a new vector which is calculated by postmultiplying this vector by the transpose of the given matrix's inverse and then normalizing the result.

        **matrix**		*MMatrix*

        **RETURNS**		*MVector*

        >>> matrix = MMatrix()
        >>> new_v = v.transformAsNormal(matrix)

        """

        return MVector(super(MVector, self).transformAsNormal(matrix))


class MVectorArray(om.MVectorArray):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'

    The MVectorArray class provides an array of MVector elements using a common array interface and reference
    semantics. See Working with M*Array Classes for more details.

    Trying to override muliply functionality causes Maya to crash. If user multiplys this array by a int value
    it will return base version of OpenMaya.MVectorArray as a result.
    """


    def __init__(self, *args):

        super(MVectorArray, self).__init__(*args)


    def __reduce__(self):

        return (MVectorArray, (tuple([tuple(vect) for vect in self]),))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __getitem__(self, i):

        return MVector(super(MVectorArray, self).__getitem__(i))


    def __getslice__(self, i, j):

        return MVectorArray(super(MVectorArray, self).__getslice__(i, j))


    def __repr__(self):

        return super(MVectorArray, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.")


    def __str__(self):

        return super(MVectorArray, self).__str__().replace("maya.api.OpenMaya.", "MPyNode.")


    def __add__(self, y):

        ##---some reason calling __add__ directly on the parent class causes a crash (WTF?)----##
        return MVectorArray(om.MVectorArray(self) + y)


    def __iadd__(self, y):

        return MVectorArray(super(MVectorArray, self).__iadd__(y))
