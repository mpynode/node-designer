import maya.mel as mel


class MUndo(object):
    """
    Wraps a call to the given python function in MEL so it occupies a single undo slot.
    """

    _call_func = None
    _call_args = None
    _call_kargs = None
    _call_return = None
    
    
    def __init__(self, func, *args, **kwargs):
        """
        Create a new MUndo wrapper object around the given python function with the given arguments.
        
        **func**		python function object to call. Note that this is not the string name of the function but
        				instead the function itself.
        
        **args**		args supported by the function passed into the *func* arg
        
        **kargs**		args supported by the function passed into the *func* arg
        
        *RETURNS*		None
        
        >>> ##the ending '()' calls the MUndo object as soon as its created
        >>> MUndo(myCoolFunc, arg1, arg2, keyword1="test", keyword2="test2")()
        
        """

        self.func = func
        self.args = args
        self.kwargs = kwargs
        

    @classmethod
    def _run(cls):

        func = cls._call_func
        args = cls._call_args
        kargs = cls._call_kargs

        cls._call_return = func(*args, **kargs)
        

    def __call__(self, *args):

        self.__class__._call_func = self.func
        self.__class__._call_args = self.args
        self.__class__._call_kargs = self.kwargs

        mel.eval("python(\"from mpylib import MUndo; MUndo._run()\")")

        return self.__class__._call_return