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

        try:
            super().__init__(*args) # python3
        except:
            super(MAngle, self).__init__(*args) # python2
            


    def __reduce__(self):

        return (MAngle, (self.asRadians(), MAngle.kRadians))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __repr__(self):

        try:
            return super().__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MAngle, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


class MColor(om.MColor):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """

    def __init__(self, clr=None, model=om.MColor.kRGB, dataType=om.MColor.kFloat):

        self._model = model
        self._data_type = dataType

        if clr:
            try:
                super().__init__(clr, model=model, dataType=dataType) # python3
            except:
                super(MColor, self).__init__(clr, model=model, dataType=dataType) # python2
                

        else:
            try:
                super().__init__() # python3
            except:
                super(MColor, self).__init__() # python2
                


    def __reduce__(self):

        return (MColor, ((self.r, self.g, self.b, self.a), self._model, self._data_type))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __add__(self, y):

        try:
            return MColor(super().__add__(y)) # python3
        except:
            return MColor(super(MColor, self).__add__(y)) # python2
            


    def __radd__(self, y):

        try:
            return MColor(super().__radd__(y)) # python3
        except:
            return MColor(super(MColor, self).__radd__(y)) # python2
            


    def __iadd__(self, y):

        try:
            return MColor(super().__iadd__(y)) # python3
        except:
            return MColor(super(MColor, self).__iadd__(y)) # python2
            


    def __mul__(self, y):

        try:
            return  MColor(super().__mul__(y)) # python3
        except:
            return  MColor(super(MColor, self).__mul__(y)) # python2
            


    def __rmul__(self, y):

        try:
            return  MColor(super().__rmul__(y)) # python3
        except:
            return  MColor(super(MColor, self).__rmul__(y)) # python2
            


    def __imul__(self, y):

        try:
            return  MColor(super().__imul__(y)) # python3
        except:
            return  MColor(super(MColor, self).__imul__(y)) # python2
            


    def __div__(self, y):

        try:
            return MColor(super().__div__(y)) # python3
        except:
            return MColor(super(MVector, self).__div__(y)) # python2
            


    def __idiv__(self, y):

        try:
            return MColor(super().__idiv__(y)) # python3
        except:
            return MColor(super(MVector, self).__idiv__(y)) # python2
            


    def __rdiv__(self, y):

        try:
            return MColor(super().__rdiv__(y)) # python3
        except:
            return MColor(super(MVector, self).__rdiv__(y)) # python2
            


    def __str__(self):

        return str((self.r, self.g, self.b, self.a))


    def __repr__(self):

        try:
            return super().__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MColor, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


    def setColor(self, clr, model=om.MColor.kRGB, dataType=om.MColor.kFloat):
        """
        Override of the base class version to add functionality
        """

        self._model = model
        self._data_type = dataType

        try:
            super().setColor(clr, model=model, dataType=dataType) # python3
        except:
            super(MColor, self).setColor(clr, model=model, dataType=dataType) # python2
            


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

        try:
            super().__init__(*args) # python3
        except:
            super(MColorArray, self).__init__(*args) # python2
            


    def __reduce__(self):

        return (MColorArray, (tuple([tuple(clr) for clr in self]),))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __getitem__(self, i):

        try:
            return MColor(super().__getitem__(i)) # python3
        except:
            return MColor(super(MColorArray, self).__getitem__(i)) # python2
            


    def __getslice__(self, i, j):

        try:
            return MColorArray(super().__getslice__(i, j)) # python3
        except:
            return MColorArray(super(MVectorArray, self).__getslice__(i, j)) # python2
            


    def __repr__(self):

        try:
            return super().__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MColorArray, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


    def __str__(self):

        try:
            return super().__str__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MColorArray, self).__str__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


class MEulerRotation(om.MEulerRotation):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args, **kargs):

        try:
            super().__init__(*args, **kargs) # python3
        except:
            super(MEulerRotation, self).__init__(*args, **kargs) # python2
            


    def __reduce__(self):

        return (MEulerRotation, (self.x, self.y, self.z, self.order))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __str__(self):

        return str((self.x, self.y, self.z))


    def __repr__(self):

        try:
            return super().__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MEulerRotation, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


    def __add__(self, y):

        try:
            return MEulerRotation(super().__add__(y)) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).__add__(y)) # python2
            


    def __radd__(self, y):

        try:
            return MEulerRotation(super().__radd__(y)) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).__radd__(y)) # python2
            


    def __iadd__(self, y):

        try:
            return MEulerRotation(super().__iadd__(y)) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).__iadd__(y)) # python2
            


    def __sub__(self, y):

        try:
            return MEulerRotation(super().__sub__(y)) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).__sub__(y)) # python2
            


    def __rsub__(self, y):

        try:
            return MEulerRotation(super().__rsub__(y)) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).__rsub__(y)) # python2
            


    def __isub__(self, y):

        try:
            return MEulerRotation(super().__isub__(y)) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).__isub__(y)) # python2
            


    def __mul__(self, y):

        try:
            return MEulerRotation(super().__mul__(y)) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).__mul__(y)) # python2
            


    def __rmul__(self, y):

        try:
            return MEulerRotation(super().__rmul__(y)) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).__rmul__(y)) # python2
            


    def __imul__(self, y):

        try:
            return MEulerRotation(super().__imul__(y)) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).__imul__(y)) # python2
            


    def alternateSolution(self):

        try:
            return MEulerRotation(super().alternateSolution()) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).alternateSolution()) # python2
            


    def asMatrix(self):

        try:
            return MMatrix(super().asMatrix()) # python3
        except:
            return MMatrix(super(MEulerRotation, self).asMatrix()) # python2
            


    def asQuaternion(self):

        try:
            return MQuaternion(super().asQuaternion()) # python3
        except:
            return MQuaternion(super(MEulerRotation, self).asQuaternion()) # python2
            


    def asVector(self):

        try:
            return MVector(super().asVector()) # python3
        except:
            return MVector(super(MEulerRotation, self).asVector()) # python2
            


    def bound(self):

        try:
            return MEulerRotation(super().bound()) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).bound()) # python2
            


    def closestCut(self, target):

        try:
            return MEulerRotation(super().closestCut(target)) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).closestCut(target)) # python2
            


    def closestSolution(self, target):

        try:
            return MEulerRotation(super().closestSolution(target)) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).closestSolution(target)) # python2
            


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

        try:
            return MEulerRotation(super().inverse()) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).inverse()) # python2
            


    def reorder(self, order):

        try:
            return MEulerRotation(super().reorder(order)) # python3
        except:
            return MEulerRotation(super(MEulerRotation, self).reorder(order)) # python2
            


class MFnMesh(om.MFnMesh):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args, **kargs):

        try:
            super().__init__(*args, **kargs) # python3
        except:
            super(MFnMesh, self).__init__(*args, **kargs) # python2
            


    def getPoints(self, space=om.MSpace.kObject):

        try:
            return MPointArray(super().getPoints(space)) # python3
        except:
            return MPointArray(super(MFnMesh, self).getPoints(space)) # python2
            


class MFnNurbsCurve(om.MFnNurbsCurve):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args, **kargs):

        try:
            super().__init__(*args, **kargs) # python3
        except:
            super(MFnNurbsCurve, self).__init__(*args, **kargs) # python2
            


    def closestPoint(self, test_pnt, guess=None, tolerance=om.MFnNurbsCurve.kPointTolerance, space=om.MSpace.kObject):

        try:
            pnt, param = super().closestPoint(test_pnt, guess, tolerance, space) # python3
        except:
            pnt, param = super(MFnNurbsCurve, self).closestPoint(test_pnt, guess, tolerance, space) # python2
            

        return MPoint(pnt), param


    def cvPosition(self, index, space=om.MSpace.kObject):

        try:
            return MPoint(super().cvPosition(index, space)) # python3
        except:
            return MPoint(super(MFnNurbsCurve, self).cvPosition(index, space)) # python2
            


    def cvPositions(self, space=om.MSpace.kObject):

        try:
            return MPointArray(super().cvPositions(space)) # python3
        except:
            return MPointArray(super(MFnNurbsCurve, self).cvPositions(space)) # python2
            


    def getDerivativesAtParam(self, param, space=om.MSpace.kObject, dUU=False):

        try:
            result = super().getDerivativesAtParam(param, space=space, dUU=dUU) # python3
        except:
            result = super(MFnNurbsCurve, self).getDerivativesAtParam(param, space=space, dUU=dUU) # python2
            

        if len(result) < 3:
            return MPoint(result[0]), MVector(result[1])

        else:
            return MPoint(result[0]), MVector(result[1]), MVector(result[2])


    def getPointAtParam(self, param, space=om.MSpace.kObject):

        try:
            return MPoint(super().getPointAtParam(param, space)) # python3
        except:
            return MPoint(super(MFnNurbsCurve, self).getPointAtParam(param, space)) # python2
            


    def normal(self, param, space=om.MSpace.kObject):

        try:
            return MVector(super().normal(param, space)) # python3
        except:
            return MVector(super(MFnNurbsCurve, self).normal(param, space)) # python2
            


    def tangent(self, param, space=om.MSpace.kObject):

        try:
            return MVector(super().tangent(param, space)) # python3
        except:
            return MVector(super(MFnNurbsCurve, self).tangent(param, space)) # python2
            



class MMatrix(om.MMatrix):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args):

        try:
            super().__init__(*args) # python3
        except:
            super(MMatrix, self).__init__(*args) # python2
            


    def __reduce__(self):

        return (MMatrix, (tuple(self),))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __add__(self, y):

        try:
            return MMatrix(super().__add__(y)) # python3
        except:
            return MMatrix(super(MMatrix, self).__add__(y)) # python2
            


    def __radd__(self, y):

        try:
            return MMatrix(super().__radd__(y)) # python3
        except:
            return MMatrix(super(MMatrix, self).__radd__(y)) # python2
            


    def __iadd__(self, y):

        try:
            return MMatrix(super().__iadd__(y)) # python3
        except:
            return MMatrix(super(MMatrix, self).__iadd__(y)) # python2
            


    def __sub__(self, y):

        try:
            return MMatrix(super().__sub__(y)) # python3
        except:
            return MMatrix(super(MMatrix, self).__sub__(y)) # python2
            


    def __rsub__(self, y):

        try:
            return MMatrix(super().__rsub__(y)) # python3
        except:
            return MMatrix(super(MMatrix, self).__rsub__(y)) # python2
            


    def __isub__(self, y):

        try:
            return MMatrix(super().__isub__(y)) # python3
        except:
            return MMatrix(super(MMatrix, self).__isub__(y)) # python2
            


    def __mul__(self, y):

        try:
            result = super().__mul__(y) # python3
        except:
            result = super(MMatrix, self).__mul__(y) # python2
            

        if result is NotImplemented:
            return NotImplemented

        return MMatrix(result)


    def __rmul__(self, y):

        try:
            return MMatrix(super().__rmul__(y)) # python3
        except:
            return MMatrix(super(MMatrix, self).__rmul__(y)) # python2
            


    def __imul__(self, y):

        try:
            return MMatrix(super().__imul__(y)) # python3
        except:
            return MMatrix(super(MMatrix, self).__imul__(y)) # python2
            


    def adjoint(self):
        """
        Returns a new matrix containing this matrix's adjoint.
        """

        try:
            return MMatrix(super().adjoint()) # python3
        except:
            return MMatrix(super(MMatrix, self).adjoint()) # python2
            


    def homogenize(self):
        """
        Returns a new matrix containing the homogenized version of this matrix.
        """

        try:
            return MMatrix(super().homogenize()) # python3
        except:
            return MMatrix(super(MMatrix, self).homogenize()) # python2
            


    def inverse(self):
        """
        Returns a new matrix containing this matrix's inverse.
        """

        try:
            return MMatrix(super().inverse()) # python3
        except:
            return MMatrix(super(MMatrix, self).inverse()) # python2
            


    def transpose(self):
        """
        Returns a new matrix containing this matrix's inverse.
        """

        try:
            return MMatrix(super().transpose()) # python3
        except:
            return MMatrix(super(MMatrix, self).transpose()) # python2
            


class MMatrixArray(om.MMatrixArray):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args):

        try:
            super().__init__(*args) # python3
        except:
            super(MMatrixArray, self).__init__(*args) # python2
            


    def __reduce__(self):

        return (MMatrixArray, (tuple([tuple(mat) for mat in self]),))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __getitem__(self, i):

        try:
            return MMatrix(super().__getitem__(i)) # python3
        except:
            return MMatrix(super(MMatrixArray, self).__getitem__(i)) # python2
            


    def __getslice__(self, i, j):

        try:
            return MMatrixArray(super().__getslice__(i, j)) # python3
        except:
            return MMatrixArray(super(MMatrixArray, self).__getslice__(i, j)) # python2
            


    def __repr__(self):

        try:
            return super().__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MMatrixArray, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


    def __str__(self):

        try:
            return super().__str__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MMatrixArray, self).__str__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


class MPoint(om.MPoint):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args):

        try:
            super().__init__(*args) # python3
        except:
            super(MPoint, self).__init__(*args) # python2
            


    def __reduce__(self):

        return (MPoint, (self.x, self.y, self.z, self.w))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __add__(self, y):

        try:
            return MPoint(super().__add__(y)) # python3
        except:
            return MPoint(super(MPoint, self).__add__(y)) # python2
            


    def __radd__(self, y):

        try:
            return MPoint(super().__radd__(y)) # python3
        except:
            return MPoint(super(MPoint, self).__radd__(y)) # python2
            


    def __iadd__(self, y):

        try:
            return MPoint(super().__iadd__(y)) # python3
        except:
            return MPoint(super(MPoint, self).__iadd__(y)) # python2
            


    def __mul__(self, y):

        try:
            return  MPoint(super().__mul__(y)) # python3
        except:
            return  MPoint(super(MPoint, self).__mul__(y)) # python2
            


    def __rmul__(self, y):

        try:
            return  MPoint(super().__rmul__(y)) # python3
        except:
            return  MPoint(super(MPoint, self).__rmul__(y)) # python2
            


    def __imul__(self, y):

        try:
            return  MPoint(super().__imul__(y)) # python3
        except:
            return  MPoint(super(MPoint, self).__imul__(y)) # python2
            


    def __div__(self, y):

        try:
            return MPoint(super().__div__(y)) # python3
        except:
            return MPoint(super(MPoint, self).__div__(y)) # python2
            


    def __rdiv__(self, y):

        try:
            return MPoint(super().__rdiv__(y)) # python3
        except:
            return MPoint(super(MPoint, self).__rdiv__(y)) # python2
            


    def __sub__(self, y):

        try:
            diff = super().__sub__(y) # python3
        except:
            diff = super(MPoint, self).__sub__(y) # python2
            

        if type(diff) == om.MVector:
            return MVector(diff)

        return MPoint(diff)


    def __rsub__(self, y):

        try:
            diff = super().__rsub__(y) # python3
        except:
            diff = super(MPoint, self).__rsub__(y) # python2
            

        if type(diff) == om.MVector:
            return MVector(diff)

        return MPoint(diff)


    def __isub__(self, y):
        """
        In-place subtract
        """

        try:
            return MPoint(super().__isub__(y)) # python3
        except:
            return MPoint(super(MPoint, self).__isub__(y)) # python2
            


    def __str__(self):

        return str((self.x, self.y, self.z, self.w))


    def __repr__(self):

        try:
            return super().__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MPoint, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


class MPointArray(om.MPointArray):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args):

        try:
            super().__init__(*args) # python3
        except:
            super(MPointArray, self).__init__(*args) # python2
            


    def __reduce__(self):

        return (MPointArray, (tuple([tuple(pnt) for pnt in self]),))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __add__(self, y):

        ##---some reason calling __add__ directly on the parent class causes a crash (WTF?)----##
        return MPointArray(om.MPointArray(self) + y)


    def __iadd__(self, y):

        try:
            return MPointArray(super().__iadd__(y)) # python3
        except:
            return MPointArray(super(MVectorArray, self).__iadd__(y)) # python2
            


    def __getitem__(self, i):

        try:
            return MPoint(super().__getitem__(i)) # python3
        except:
            return MPoint(super(MPointArray, self).__getitem__(i)) # python2
            


    def __getslice__(self, i, j):

        try:
            return MPointArray(super().__getslice__(i, j)) # python3
        except:
            return MPointArray(super(MPointArray, self).__getslice__(i, j)) # python2
            


    def __repr__(self):

        try:
            return super().__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MPointArray, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


    def __str__(self):

        try:
            return super().__str__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MPointArray, self).__str__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


class MQuaternion(om.MQuaternion):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """


    def __init__(self, *args):

        try:
            super().__init__(*args) # python3
        except:
            super(MQuaternion, self).__init__(*args) # python2
            


    def __reduce__(self):

        return (MQuaternion, (self.x, self.y, self.z, self.w))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __str__(self):

        return str((self.x, self.y, self.z, self.w))


    def __repr__(self):

        try:
            return super().__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MQuaternion, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


    def __add__(self, y):

        try:
            return MQuaternion(super().__add__(y)) # python3
        except:
            return MQuaternion(super(MQuaternion, self).__add__(y)) # python2
            


    def __radd__(self, y):

        try:
            return MQuaternion(super().__radd__(y)) # python3
        except:
            return MQuaternion(super(MQuaternion, self).__radd__(y)) # python2
            


    def __sub__(self, y):

        try:
            return MQuaternion(super().__sub__(y)) # python3
        except:
            return MQuaternion(super(MQuaternion, self).__sub__(y)) # python2
            


    def __rsub__(self, y):

        try:
            return MQuaternion(super().__rsub__(y)) # python3
        except:
            return MQuaternion(super(MQuaternion, self).__rsub__(y)) # python2
            


    def __mul__(self, y):

        try:
            return MQuaternion(super().__mul__(y)) # python3
        except:
            return MQuaternion(super(MQuaternion, self).__mul__(y)) # python2
            


    def __rmul__(self, y):

        try:
            return MQuaternion(super().__rmul__(y)) # python3
        except:
            return MQuaternion(super(MQuaternion, self).__rmul__(y)) # python2
            


    def __imul__(self, y):

        try:
            return MQuaternion(super().__imul__(y)) # python3
        except:
            return MQuaternion(super(MQuaternion, self).__imul__(y)) # python2
            


    def __neg__(self):
        """
        Component-by-component negation
        """

        try:
            return MQuaternion(super().__neg__()) # python3
        except:
            return MQuaternion(super(MQuaternion, self).__neg__()) # python2
            


    def asAxisAngle(self):
        """
        Returns the rotation as a tuple containing an axis vector and an angle in radians about that axis.
        """

        try:
            vect, angle = super().asAxisAngle() # python3
        except:
            vect, angle = super(MQuaternion, self).asAxisAngle() # python2
            

        return MVector(vect), angle


    def asEulerRotation(self):
        """
        Returns the rotation as an equivalent MEulerRotation.
        """

        try:
            return MEulerRotation(super().asEulerRotation()) # python3
        except:
            return MEulerRotation(super(MQuaternion, self).asEulerRotation()) # python2
            


    def asMatrix(self):
        """
        Returns the rotation as an equivalent rotation matrix.
        """

        try:
            return MMatrix(super().asMatrix()) # python3
        except:
            return MMatrix(super(MQuaternion, self).asMatrix()) # python2
            


    def conjugate(self):
        """
        Returns the conjugate of this quaternion (i.e. x, y and z components negated).
        """

        try:
            return MQuaternion(super().conjugate()) # python3
        except:
            return MQuaternion(super(MQuaternion, self).conjugate()) # python2
            


    def exp(self):
        """
        Returns a new quaternion containing the exponent of this one.
        """

        try:
            return MQuaternion(super().exp()) # python3
        except:
            return MQuaternion(super(MQuaternion, self).exp()) # python2
            


    def inverse(self):
        """
        Returns a new quaternion containing the inverse of this one.
        """

        try:
            return MQuaternion(super().inverse()) # python3
        except:
            return MQuaternion(super(MQuaternion, self).inverse()) # python2
            


    def log(self):
        """
        Returns a new quaternion containing the log of this one.
        """

        try:
            return MQuaternion(super().log()) # python3
        except:
            return MQuaternion(super(MQuaternion, self).log()) # python2
            


    def normal(self):
        """
        Returns a new quaternion containing the normalized version of this one (i.e. scaled to unit length).
        """

        try:
            return MQuaternion(super().normal()) # python3
        except:
            return MQuaternion(super(MQuaternion, self).normal()) # python2
            


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

        try:
            super().__init__(*args, **kargs) # python3
        except:
            super(MTime, self).__init__(*args, **kargs) # python2
            


    def __reduce__(self):

        return (MTime, (self.value, self.unit))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __str__(self):

        try:
            return super().__str__() # python3
        except:
            return super(MTime, self).__str__() # python2
            


    def __repr__(self):

        try:
            return super().__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MTime, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


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

        try:
            super().__init__(*args) # python3
        except:
            super(MTimeArray, self).__init__(*args) # python2
            

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

        try:
            return MTime(super().__getitem__(i)) # python3
        except:
            return MTime(super(MTimeArray, self).__getitem__(i)) # python2
            


    def __getslice__(self, i, j):

        try:
            return MTimeArray(super().__getslice__(i, j)) # python3
        except:
            return MTimeArray(super(MTimeArray, self).__getslice__(i, j)) # python2
            


    def __str__(self):

        try:
            return super().__str__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MTimeArray, self).__str__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


    def __repr__(self):

        try:
            return super().__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MTimeArray, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


class MVector(om.MVector):
    """
    Override of the Maya API class of the same name to make
    the data within the class 'picklable'
    """

    def __init__(self, *args):

        try:
            super().__init__(*args) # python3
        except:
            super(MVector, self).__init__(*args) # python2
            


    def __reduce__(self):

        return (MVector, (self.x, self.y, self.z))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __add__(self, y):

        try:
            return MVector(super().__add__(y)) # python3
        except:
            return MVector(super(MVector, self).__add__(y)) # python2
            


    def __radd__(self, y):

        try:
            return MVector(super().__radd__(y)) # python3
        except:
            return MVector(super(MVector, self).__radd__(y)) # python2
            


    def __iadd__(self, y):

        try:
            return MVector(super().__iadd__(y)) # python3
        except:
            return MVector(super(MVector, self).__iadd__(y)) # python2
            


    def __sub__(self, y):

        try:
            return MVector(super().__sub__(y)) # python3
        except:
            return MVector(super(MVector, self).__sub__(y)) # python2
            


    def __rsub__(self, y):

        try:
            return MVector(super().__rsub__(y)) # python3
        except:
            return MVector(super(MVector, self).__rsub__(y)) # python2
            


    def __isub__(self, y):
        """
        In-place subtract
        """

        try:
            return MVector(super().__isub__(y)) # python3
        except:
            return MVector(super(MVector, self).__isub__(y)) # python2
            


    def __xor__(self, y):
        """
        Cross product
        """

        try:
            return MVector(super().__xor__(y)) # python3
        except:
            return MVector(super(MVector, self).__xor__(y)) # python2
            


    def __rxor__(self, y):
        """
        Reverse cross product
        """

        try:
            return MVector(super().__rxor__(y)) # python3
        except:
            return MVector(super(MVector, self).__rxor__(y)) # python2
            


    def __mul__(self, y):

        try:
            result = super().__mul__(y) # python3
        except:
            result = super(MVector, self).__mul__(y) # python2
            

        if type(result) == om.MVector:
            return MVector(result)

        return result


    def __rmul__(self, y):

        try:
            result = super().__rmul__(y) # python3
        except:
            result = super(MVector, self).__rmul__(y) # python2
            

        if type(result) == om.MVector:
            return MVector(result)

        return result


    def __imul__(self, y):

        try:
            result = super().__imul__(y) # python3
        except:
            result = super(MVector, self).__imul__(y) # python2
            

        if type(result) == om.MVector:
            return MVector(result)

        return result


    def __div__(self, y):

        try:
            return MVector(super().__div__(y)) # python3
        except:
            return MVector(super(MVector, self).__div__(y)) # python2
            


    def __idiv__(self, y):

        try:
            return MVector(super().__idiv__(y)) # python3
        except:
            return MVector(super(MVector, self).__idiv__(y)) # python2
            


    def __rdiv__(self, y):

        try:
            return MVector(super().__rdiv__(y)) # python3
        except:
            return MVector(super(MVector, self).__rdiv__(y)) # python2
            


    def __neg__(self):
        """
        New vector which is the negative if the given vector.
        """

        try:
            return MVector(super().__neg__()) # python3
        except:
            return MVector(super(MVector, self).__neg__()) # python2
            


    def __str__(self):

        return str((self.x, self.y, self.z))


    def __repr__(self):

        try:
            return super().__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MVector, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


    def normal(self):
        """
        Returns a new vector containing the normalized version of this one.

        **RETURNS** 	*MVector*

        >>> new_v = v.normal()

        """

        try:
            return MVector(super().normal()) # python3
        except:
            return MVector(super(MVector, self).normal()) # python2
            


    def normalize(self):
        """
        Normalizes this vector in-place and returns a new reference to it.

        **RETURNS** 	*MVector*

        >>> v.normalize()

        """

        try:
            return MVector(super().normalize()) # python3
        except:
            return MVector(super(MVector, self).normalize()) # python2
            


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

        try:
            return MVector(super().rotateBy(*args)) # python3
        except:
            return MVector(super(MVector, self).rotateBy(*args)) # python2
            


    def rotateTo(self, target):
        """
        Returns the quaternion which will rotate this vector into another.

        **target**		*MVector*

        **RETURNS** 	*MQuaternion*

        >>> q = v.rotateTo(MVector(1.0, 0.0, 0.0))

        """

        try:
            return MQuaternion(super().rotateTo(target)) # python3
        except:
            return MQuaternion(super(MVector, self).rotateTo(target)) # python2
            


    def transformAsNormal(self, matrix):
        """
        Returns a new vector which is calculated by postmultiplying this vector by the transpose of the given matrix's inverse and then normalizing the result.

        **matrix**		*MMatrix*

        **RETURNS**		*MVector*

        >>> matrix = MMatrix()
        >>> new_v = v.transformAsNormal(matrix)

        """

        try:
            return MVector(super().transformAsNormal(matrix)) # python3
        except:
            return MVector(super(MVector, self).transformAsNormal(matrix)) # python2
            


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

        try:
            super().__init__(*args) # python3
        except:
            super(MVectorArray, self).__init__(*args) # python2
            


    def __reduce__(self):

        return (MVectorArray, (tuple([tuple(vect) for vect in self]),))


    def __reduce_ex__(self, protocol):

        return self.__reduce__()


    def __getitem__(self, i):

        try:
            return MVector(super().__getitem__(i)) # python3
        except:
            return MVector(super(MVectorArray, self).__getitem__(i)) # python2
            


    def __getslice__(self, i, j):

        try:
            return MVectorArray(super().__getslice__(i, j)) # python3
        except:
            return MVectorArray(super(MVectorArray, self).__getslice__(i, j)) # python2
            


    def __repr__(self):

        try:
            return super().__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MVectorArray, self).__repr__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


    def __str__(self):

        try:
            return super().__str__().replace("maya.api.OpenMaya.", "MPyNode.") # python3
        except:
            return super(MVectorArray, self).__str__().replace("maya.api.OpenMaya.", "MPyNode.") # python2
            


    def __add__(self, y):

        ##---some reason calling __add__ directly on the parent class causes a crash (WTF?)----##
        return MVectorArray(om.MVectorArray(self) + y)


    def __iadd__(self, y):

        try:
            return MVectorArray(super().__iadd__(y)) # python3
        except:
            return MVectorArray(super(MVectorArray, self).__iadd__(y)) # python2
            
