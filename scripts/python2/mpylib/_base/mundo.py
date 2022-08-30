from functools import wraps

import maya.mel as mel
import maya.cmds as mc


class MUndo(object):
    """
    Wraps a call to the given python function in MEL so it occupies a single undo slot.
    """

    _call_func = None
    _call_args = None
    _call_kargs = None
    _call_return = None


    def __init__(self, func, *args, **kargs):
        """
        __init__(func, \*args, \*\*kwargs)

            Create a new MUndo wrapper object around the given python function with the given arguments.

            Parameters
            ----------
            func : function object
                python function object to wrap and call. Note that this is not the string name of the function but
                instead the function object itself.

            args : *positional args*, optional
                positional args to pass the the wrapped function

            kargs : *keyword args*, optional
                keyword args to pass the the wrapped function

            Returns
            -------
            *None*

            Examples
            --------
            >>> ##the ending '()' calls the MUndo object as soon as its created
            >>> MUndo(myCoolFunc, arg1, arg2, keyword1="test", keyword2="test2")()
        """

        self.func = func
        self.args = args
        self.kargs = kargs


    @staticmethod
    def wrap(func):
        """
        Puts the wrapped `func` into a single Maya Undo action, then undoes it when
        the function enters the finally: block
        """

        @wraps(func)
        def _undofunc(*args, **kargs):
            try:
                mc.undoInfo(ock=True)
                return func(*args, **kargs)

            finally:
                mc.undoInfo(cck=True)
                mc.undo()

        return _undofunc


    @classmethod
    def _run(cls):

        func = cls._call_func
        args = cls._call_args
        kargs = cls._call_kargs

        cls._call_return = func(*args, **kargs)


    def __call__(self, *args):

        self.__class__._call_func = self.func
        self.__class__._call_args = self.args
        self.__class__._call_kargs = self.kargs

        mel.eval("python(\"from mpylib import MUndo; MUndo._run()\")")

        return self.__class__._call_return