import maya.cmds as mc
from collections import OrderedDict
from mpylib.nodes import MPyNode
from mpylib.api import MMatrix, MVector, MQuaternion # injectables
from maya.api.OpenMaya import MTransformationMatrix, MSpace 

'''
# Initialize a gripped node
myAwesomeGrip = 'pCube1'   # REQUIRED: The transform you want to grip.
myAwesomeController = None # OPTIONAL: None  = enums and blend value will be added to myAwesomeGrip.
                           #           str() = enums and blend value will be added to myAwesomeController.

# Initialize the grip
test = GripNode(grip=myAwesomeGrip, controller=myAwesomeController)


# Add targets  add(target, enum=None, maintain_offset=False)
# target = REQUIRED: The target you want to grip to
# enum=str() # string to give the enum corresponding to this target. If None, target node name is used
# maintain_offset=False/True # Self explanatory... could break it down to specific scale/rotate/translate components if need be
     
test.add('world',maintain_offset=True) 
test.add('ik',maintain_offset=False)
test.add('ik',enum='bananas',maintain_offset=True)
'''





class GripNode(MPyNode):
    
    INIT_INPUT_ATTRS = OrderedDict()
    INIT_INPUT_ATTRS['inMatrix0']           = {'attr_type':'matrix'}
    INIT_INPUT_ATTRS['inMatrix1']           = {'attr_type':'matrix'}
    INIT_INPUT_ATTRS['parentInverseMatrix'] = {'attr_type':'matrix'}
    INIT_INPUT_ATTRS['rotateOrder']         = {'attr_type':'int',   'minValue':0, 'maxValue':5}
    INIT_INPUT_ATTRS['weight']              = {'attr_type':'float', 'minValue':0.,'maxValue':1.,'keyable':True}
    INIT_INPUT_ATTRS['grip0']               = {'attr_type':'int','keyable':True}
    INIT_INPUT_ATTRS['grip1']               = {'attr_type':'int','keyable':True}
    
    INIT_OUTPUT_ATTRS = OrderedDict()
    #INIT_OUTPUT_ATTRS['outMatrix']          = {"attr_type":"matrix"}
    INIT_OUTPUT_ATTRS['outScale']           = {"attr_type":"vector"}
    INIT_OUTPUT_ATTRS['outRotation']        = {"attr_type":"euler"}
    INIT_OUTPUT_ATTRS['outTranslation']     = {"attr_type":"vector"}
    
    INIT_STORED_VARS = {'offsets':[MMatrix()]}

    INIT_EXPRESSION_STR = ("# Convert matrices to transformation matrices\n"
                           "target_matrix0 = om.MTransformationMatrix(inMatrix0)\n"
                           "target_matrix1 = om.MTransformationMatrix(inMatrix1)\n"
                           "\n"
                           "# Grab offsets from stored buffers\n"
                           "offset_matrix0 = om.MTransformationMatrix(self.offsets[grip0])\n"
                           "offset_matrix1 = om.MTransformationMatrix(self.offsets[grip1])\n"
                           "\n"
                           "# Extract components\n"
                           "target_scale0 = target_matrix0.scale(om.MSpace.kWorld)             # scale0\n"
                           "target_scale1 = target_matrix1.scale(om.MSpace.kWorld)             # scale1\n"
                           "target_rotation0 = target_matrix0.rotation(asQuaternion=True)      # rotation0\n"
                           "target_rotation1 = target_matrix1.rotation(asQuaternion=True)      # rotation1\n"
                           "target_translation0 = target_matrix0.translation(om.MSpace.kWorld) # translation0\n"
                           "target_translation1 = target_matrix1.translation(om.MSpace.kWorld) # translation1\n"
                           "\n"
                           "offset_scale0 = offset_matrix0.scale(om.MSpace.kWorld)             # scale0\n"
                           "offset_scale1 = offset_matrix1.scale(om.MSpace.kWorld)             # scale1\n"
                           "offset_rotation0 = offset_matrix0.rotation(asQuaternion=True)      # rotation0\n"
                           "offset_rotation1 = offset_matrix1.rotation(asQuaternion=True)      # rotation1\n"
                           "offset_translation0 = offset_matrix0.translation(om.MSpace.kWorld) # translation0\n"
                           "offset_translation1 = offset_matrix1.translation(om.MSpace.kWorld) # translation1\n"
                           "\n"
                           "\n"
                           "\n"
                           "# Interpolate scale\n"
                           "weight_ = 1-weight\n"
                           "target_scale0[0] = target_scale1[0]**weight * target_scale0[0]**weight_\n"
                           "target_scale0[1] = target_scale1[1]**weight * target_scale0[1]**weight_\n"
                           "target_scale0[2] = target_scale1[2]**weight * target_scale0[2]**weight_\n"
                           "\n"
                           "offset_scale0[0] = offset_scale1[0]**weight * offset_scale0[0]**weight_\n"
                           "offset_scale0[1] = offset_scale1[1]**weight * offset_scale0[1]**weight_\n"
                           "offset_scale0[2] = offset_scale1[2]**weight * offset_scale0[2]**weight_\n"
                           "\n"
                           "\n"
                           "# Interpolate rotation\n"
                           "target_rotation0 = om.MQuaternion.slerp(target_rotation0,target_rotation1,weight)\n"
                           "offset_rotation0 = om.MQuaternion.slerp(offset_rotation0,offset_rotation1,weight)\n"
                           "\n"
                           "\n"
                           "# Interpolate translation\n"
                           "target_translation0[0] = target_translation1[0]*weight + target_translation0[0]*weight_\n"
                           "target_translation0[1] = target_translation1[1]*weight + target_translation0[1]*weight_\n"
                           "target_translation0[2] = target_translation1[2]*weight + target_translation0[2]*weight_\n"
                           "\n"
                           "offset_translation0[0] = offset_translation1[0]*weight + offset_translation0[0]*weight_\n"
                           "offset_translation0[1] = offset_translation1[1]*weight + offset_translation0[1]*weight_\n"
                           "offset_translation0[2] = offset_translation1[2]*weight + offset_translation0[2]*weight_\n"
                           "\n"
                           "\n"
                           "# Reconstruct a matrices with interpolated data\n"
                           "target_matrix0.setScale(target_scale0,om.MSpace.kWorld)\n"
                           "target_matrix0.setRotation(target_rotation0)\n"
                           "target_matrix0.setTranslation(target_translation0, om.MSpace.kWorld)\n"
                           "\n"
                           "offset_matrix0.setScale(offset_scale0,om.MSpace.kWorld)\n"
                           "offset_matrix0.setRotation(offset_rotation0)\n"
                           "offset_matrix0.setTranslation(offset_translation0, om.MSpace.kWorld)\n"
                           "\n"
                           "\n"
                           "# Apply offset\n"
                           "outMatrix = om.MTransformationMatrix((offset_matrix0.asMatrix() * target_matrix0.asMatrix()) * parentInverseMatrix)\n"
                           "outScale       = outMatrix.scale(om.MSpace.kTransform)\n"
                           "outRotation    = outMatrix.rotation().reorder(rotateOrder)\n"
                           "outTranslation = outMatrix.translation(om.MSpace.kTransform)\n"
                           "\n")
    
    
    

    def __init__(self, grip, name=None, controller=None):
        super(GripNode, self).__init__(name)
        
        self.grip = grip
        self.controller = controller
        if not controller:
            self.controller = grip
        
        
        # Init data buffers
        self.offsets = []
        self.targets = []
        self.enums   = []
        
        # Add default enums and weight controller
        if not mc.attributeQuery('grip0', node=self.controller, exists=True):
            mc.addAttr(self.controller,ln='grip0',at='enum',en='None',keyable=True)
            mc.addAttr(self.controller,ln='grip1',at='enum',en='None',keyable=True)
            mc.addAttr(self.controller,ln='blend',at='double',minValue=0.,maxValue=1.0,keyable=True)              
            
        # Do the basic connections except the ouput, that happens when add is invoked
        self.inMatrix0 = mc.createNode('choice',n='%s_inMatrix0'%self,ss=True)
        self.inMatrix1 = mc.createNode('choice',n='%s_inMatrix1'%self,ss=True)
        #self.outMatrix = mc.createNode('decomposeMatrix',n='%s_decomposeMatrix'%self,ss=True)
        
        mc.connectAttr('%s.output'%self.inMatrix0, '%s.inMatrix0'%self)
        mc.connectAttr('%s.output'%self.inMatrix1, '%s.inMatrix1'%self)
        #mc.connectAttr('%s.outMatrix'%self, '%s.inputMatrix'%self.outMatrix)
        #mc.connectAttr('%s.ro'%self.grip, '%s.inputRotateOrder'%self.outMatrix)
        mc.connectAttr('%s.ro'%self.grip , '%s.rotateOrder'%self)  
        
        mc.connectAttr('%s.grip0'%self.controller,   '%s.selector'%self.inMatrix0)
        mc.connectAttr('%s.grip1'%self.controller,   '%s.selector'%self.inMatrix1)
        mc.connectAttr('%s.grip0'%self.controller,   '%s.grip0'%self)
        mc.connectAttr('%s.grip1'%self.controller,   '%s.grip1'%self)
        mc.connectAttr('%s.blend'%self.controller,   '%s.weight'%self)
        mc.connectAttr('%s.parentInverseMatrix'%self.grip , '%s.parentInverseMatrix'%self)  
        
        
        


    def add(self, target, enum=None, maintain_offset=True, offset_scale=True, offset_rotation=True, offset_translation=True):
        
        # If no enumname given, use the target name
        if not enum:
            enum = target
            
            
        # Test to see if this is the first time add is invoked
        init_plug = not self.enums
        
        
        # Compute offset and append to existing enums
        twm = mc.getAttr('%s.wm'%target)    # world matrix of the grip target
        nwm = mc.getAttr('%s.wm'%self.grip) # world matrix of the gripped node
        
        if maintain_offset:
            offset = MTransformationMatrix(MMatrix(nwm) * MMatrix(twm).inverse())
            if not offset_scale:
                offset.setScale(MVector(1,1,1),MSpace.kTransform)
                
            if not offset_rotation:
                offset.setRotation(MQuaternion(0,0,0,1))
                
            if not offset_translation:
                offset.setTranslation(MVector(0,0,0),MSpace.kTransform)

            offset = MMatrix(offset.asMatrix())
            
            
        else:
            offset = MMatrix() # no offset (identity matrix)
        
        
        # Append buffers
        self.offsets.append(offset)
        self.enums.append(enum)
        self.targets.append(target)
        
        
        # Inject offsets
        self.setStoredVariable('offsets',self.offsets)
        
        
        # Set enums and connect to input matrices
        index = len(self.enums)-1
        mc.connectAttr('%s.wm'%target, '%s.input[%s]'%(self.inMatrix0,index))
        mc.connectAttr('%s.wm'%target, '%s.input[%s]'%(self.inMatrix1,index))   
        
        mc.addAttr('%s.grip0'%self.controller, e=True, en=':'.join(self.enums)+':')
        mc.addAttr('%s.grip1'%self.controller, e=True, en=':'.join(self.enums)+':')     
        
        
        # Plug node output to gripped node
        if init_plug:
            #mc.connectAttr('%s.outputScale'%self.outMatrix,     '%s.s'%self.grip, force=True)
            #mc.connectAttr('%s.outputRotate'%self.outMatrix,    '%s.r'%self.grip, force=True)
            #mc.connectAttr('%s.outputTranslate'%self.outMatrix, '%s.t'%self.grip, force=True)    
            mc.connectAttr('%s.outScale'%self,       '%s.s'%self.grip, force=True)
            mc.connectAttr('%s.outRotation'%self,    '%s.r'%self.grip, force=True)
            mc.connectAttr('%s.outTranslation'%self, '%s.t'%self.grip, force=True)    
            


        
     
            
        


            
    
        
