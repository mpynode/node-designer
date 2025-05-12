from .mpynode_obj import MPyNode

from  . import mpynode_obj_cy_win_2024 as mpynode_obj_cy


class MPyNodeC(MPyNode):
    

    def _getFloatInput(self, data_block, plug, is_array=False):
        """
        Get the given plugs input value as a float. Returns a float value or tuple of floats
        depending on the is_array arg.
        """
        
        return mpynode_obj_cy._getFloatInput(self, data_block, plug, is_array)
    
    
    def _getIntInput(self, data_block, plug, is_array=False):
        """
        Get the given plugs input value as a float. Returns a float value or tuple of floats
        depending on the is_array arg.
        """
        
        return mpynode_obj_cy._getIntInput(self, data_block, plug, is_array)