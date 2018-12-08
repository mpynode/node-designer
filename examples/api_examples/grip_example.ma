//Maya ASCII 2018ff08 scene
//Name: grip_example.ma
//Last modified: Fri, Nov 16, 2018 05:57:31 PM
//Codeset: 1252
requires maya "2018ff08";
requires -nodeType "mPyNode" "mpynode_plugin.py" "1.0";
currentUnit -linear centimeter -angle degree -time ntsc;
fileInfo "application" "maya";
fileInfo "product" "Maya 2018";
fileInfo "version" "2018";
fileInfo "cutIdentifier" "201804211841-f3d65dda2a";
fileInfo "osv" "Microsoft Windows 8 Business Edition, 64-bit  (Build 9200)\n";
createNode transform -shared -name "persp";
	rename -uuid "85014E0F-495E-C183-9872-4D99BF9E1694";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 15.254189022962764 16.051828227015463 27.114779600204454 ;
	setAttr ".rotate" -type "double3" -24.938352729603075 27.000000000000917 -8.9240499230933267e-16 ;
createNode camera -shared -name "perspShape" -parent "persp";
	rename -uuid "CBFFEE1C-4C94-C5EA-705D-7CBC034095B1";
	setAttr -keyable off ".visibility" no;
	setAttr ".focalLength" 34.999999999999993;
	setAttr ".centerOfInterest" 36.465577624700948;
	setAttr ".imageName" -type "string" "persp";
	setAttr ".depthName" -type "string" "persp_depth";
	setAttr ".maskName" -type "string" "persp_mask";
	setAttr ".homeCommand" -type "string" "viewSet -p %camera";
createNode transform -shared -name "top";
	rename -uuid "75FA28AD-4AB9-1AFD-E141-B3A4A241B2C3";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 0 1000.1 0 ;
	setAttr ".rotate" -type "double3" -89.999999999999986 0 0 ;
createNode camera -shared -name "topShape" -parent "top";
	rename -uuid "53A34E8B-4E83-BA30-BEF5-CCB0C85CDD3F";
	setAttr -keyable off ".visibility" no;
	setAttr ".renderable" no;
	setAttr ".centerOfInterest" 1000.1;
	setAttr ".orthographicWidth" 30;
	setAttr ".imageName" -type "string" "top";
	setAttr ".depthName" -type "string" "top_depth";
	setAttr ".maskName" -type "string" "top_mask";
	setAttr ".homeCommand" -type "string" "viewSet -t %camera";
	setAttr ".orthographic" yes;
createNode transform -shared -name "front";
	rename -uuid "168DB0E4-419A-E51B-FA00-6C9F6459B94D";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 0 0 1000.1 ;
createNode camera -shared -name "frontShape" -parent "front";
	rename -uuid "62483B4C-4E9B-775C-E9FE-2EA47C44AB9B";
	setAttr -keyable off ".visibility" no;
	setAttr ".renderable" no;
	setAttr ".centerOfInterest" 1000.1;
	setAttr ".orthographicWidth" 30;
	setAttr ".imageName" -type "string" "front";
	setAttr ".depthName" -type "string" "front_depth";
	setAttr ".maskName" -type "string" "front_mask";
	setAttr ".homeCommand" -type "string" "viewSet -f %camera";
	setAttr ".orthographic" yes;
createNode transform -shared -name "side";
	rename -uuid "6578B9E0-44D9-33F6-D161-5D809E0E8A2A";
	setAttr ".visibility" no;
	setAttr ".translate" -type "double3" 1000.1 0 0 ;
	setAttr ".rotate" -type "double3" 0 89.999999999999986 0 ;
createNode camera -shared -name "sideShape" -parent "side";
	rename -uuid "757809EC-44F5-7F9A-C8C5-9ABE5097EF97";
	setAttr -keyable off ".visibility" no;
	setAttr ".renderable" no;
	setAttr ".centerOfInterest" 1000.1;
	setAttr ".orthographicWidth" 30;
	setAttr ".imageName" -type "string" "side";
	setAttr ".depthName" -type "string" "side_depth";
	setAttr ".maskName" -type "string" "side_mask";
	setAttr ".homeCommand" -type "string" "viewSet -s %camera";
	setAttr ".orthographic" yes;
createNode transform -name "pCube1";
	rename -uuid "7C3EB870-499A-747F-FA84-D3A2555D8A7B";
	addAttr -cachedInternally true -keyable true -shortName "grip0" -longName "grip0" 
		-minValue 0 -maxValue 2 -enumName "world:ik:bananas" -attributeType "enum";
	addAttr -cachedInternally true -keyable true -shortName "grip1" -longName "grip1" 
		-minValue 0 -maxValue 2 -enumName "world:ik:bananas" -attributeType "enum";
	addAttr -cachedInternally true -keyable true -shortName "blend" -longName "blend" 
		-minValue 0 -maxValue 1 -attributeType "double";
	setAttr -keyable on ".grip0";
	setAttr -keyable on ".grip1" 1;
	setAttr -keyable on ".blend";
createNode mesh -name "pCubeShape1" -parent "pCube1";
	rename -uuid "E92BF643-4711-E494-27DB-F4A401EA25B5";
	setAttr -keyable off ".visibility";
	setAttr ".visibleInReflections" yes;
	setAttr ".visibleInRefractions" yes;
	setAttr ".uvSet[0].uvSetName" -type "string" "map1";
	setAttr ".currentUVSet" -type "string" "map1";
	setAttr ".displayColorChannel" -type "string" "Ambient+Diffuse";
	setAttr ".collisionOffsetVelocityMultiplier[0]"  0 1 1;
	setAttr ".collisionDepthVelocityMultiplier[0]"  0 1 1;
createNode transform -name "annotationLocator1" -parent "pCube1";
	rename -uuid "67334952-4CC7-C643-4A95-55A61A02C872";
	setAttr ".translate" -type "double3" -5.5511151231257827e-17 0 -6.9388939039072284e-18 ;
	setAttr ".scale" -type "double3" 1.0000000000000002 1.0000000000000002 1 ;
createNode locator -name "annotationLocator1Shape" -parent "annotationLocator1";
	rename -uuid "4E5F9097-49D0-229C-C16B-9FB73CF07719";
	setAttr -keyable off ".visibility";
	setAttr ".localScale" -type "double3" 0 0 0 ;
createNode transform -name "annotation1" -parent "annotationLocator1";
	rename -uuid "E42D93A9-43BB-A95E-5EA9-0FBFD61A359E";
	setAttr ".translate" -type "double3" 0.50000000000000022 2.0956398464093731 0.5 ;
createNode annotationShape -name "annotationShape1" -parent "annotation1";
	rename -uuid "3154CF20-4DE7-FFE7-8B16-EEAB5FA197DC";
	setAttr -keyable off ".visibility";
	setAttr ".text" -type "string" "Gripped Object";
createNode transform -name "world";
	rename -uuid "F75CB373-42E5-3219-F420-C48FBA2A67D3";
createNode locator -name "worldShape" -parent "|world";
	rename -uuid "D2823BCE-42C1-CFD0-72B6-F08F1CD529F5";
	setAttr -keyable off ".visibility";
createNode transform -name "annotationLocator2" -parent "|world";
	rename -uuid "A6ABF127-4FE2-9B30-8213-09915278ADDE";
createNode locator -name "annotationLocator2Shape" -parent "annotationLocator2";
	rename -uuid "4E098ACB-4F90-B7DA-EBD6-EF9812A52541";
	setAttr -keyable off ".visibility";
	setAttr ".localScale" -type "double3" 0 0 0 ;
createNode transform -name "annotation2" -parent "annotationLocator2";
	rename -uuid "56436144-485C-4C3B-F225-83BEF9A0077B";
	setAttr ".translate" -type "double3" 1 3.2677388175026758 1 ;
createNode annotationShape -name "annotationShape2" -parent "annotation2";
	rename -uuid "13C76B50-4102-F865-4B8F-818440D2AC72";
	setAttr -keyable off ".visibility";
	setAttr ".text" -type "string" "WORLD";
createNode transform -name "ik";
	rename -uuid "7923BD8D-41CB-F6C7-A3DD-32BEEB7A821B";
createNode locator -name "ikShape" -parent "ik";
	rename -uuid "5B149984-4C08-1AA0-422F-FD98419C2748";
	setAttr -keyable off ".visibility";
createNode transform -name "annotationLocator3" -parent "ik";
	rename -uuid "A7A2C93D-4014-BE97-B913-48922674CFCA";
	setAttr ".translate" -type "double3" -1.7763568394002505e-15 1.7763568394002505e-15 
		0 ;
	setAttr ".scale" -type "double3" 0.99999999999999978 0.99999999999999989 0.99999999999999989 ;
createNode locator -name "annotationLocator3Shape" -parent "annotationLocator3";
	rename -uuid "2489F31B-4102-D3C3-2EAD-488E182F4CA2";
	setAttr -keyable off ".visibility";
	setAttr ".localScale" -type "double3" 0 0 0 ;
createNode transform -name "annotation3" -parent "annotationLocator3";
	rename -uuid "2EB6D695-4F62-41F1-B2AF-CCBBBC3D1313";
	setAttr ".translate" -type "double3" 1.5385820664508039 1.5951418014199179 1.8277396647276913 ;
	setAttr ".scale" -type "double3" 1.0000000000000002 1 1 ;
createNode annotationShape -name "annotationShape3" -parent "annotation3";
	rename -uuid "38179D1C-4CA9-958E-8681-63B621A70F4F";
	setAttr -keyable off ".visibility";
	setAttr ".text" -type "string" "IK";
createNode lightLinker -shared -name "lightLinker1";
	rename -uuid "F6446E3A-4560-6BB0-DF0A-51B3591B43DB";
	setAttr -size 2 ".link";
	setAttr -size 2 ".shadowLink";
createNode shapeEditorManager -name "shapeEditorManager";
	rename -uuid "FC961D97-4AC8-4BC0-EFA4-229150BBF138";
createNode poseInterpolatorManager -name "poseInterpolatorManager";
	rename -uuid "E1379760-42BB-BA35-D3B3-A8923CD6A050";
createNode displayLayerManager -name "layerManager";
	rename -uuid "F9D40037-4050-8F02-8789-2EA596DA9D38";
createNode displayLayer -name "defaultLayer";
	rename -uuid "95AFCCA5-44D1-7BE6-B34B-A68F96DC6F20";
createNode renderLayerManager -name "renderLayerManager";
	rename -uuid "30C5D98F-43D0-F60E-2AE0-FBA4CAF437E4";
createNode renderLayer -name "defaultRenderLayer";
	rename -uuid "52815F30-4F45-7A19-E0D1-37B72C5E4FAB";
	setAttr ".global" yes;
createNode polyCube -name "polyCube1";
	rename -uuid "80662E58-4C4E-1608-5C2B-87916FA94D52";
	setAttr ".createUVs" 4;
createNode animCurveTL -name "ik_translateX";
	rename -uuid "C7C03311-40BD-6E51-4590-4092DF9A68E6";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  1 12.028235472836004 60 10.614463084154531
		 120 12.028235472836004;
createNode animCurveTL -name "ik_translateY";
	rename -uuid "8B233F7C-43BC-1930-BB6E-23A7BAA69F18";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  1 3.9557450269427714 60 11.816872225143461
		 120 3.9557450269427714;
createNode animCurveTL -name "ik_translateZ";
	rename -uuid "2425E16B-4AE9-5CAF-7EE9-32AB52CA1F2A";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  1 0.040186512870897091 60 -2.0420784813118926
		 120 0.040186512870897091;
createNode animCurveTA -name "ik_rotateX";
	rename -uuid "B2D4BAD3-480E-AB6F-50F0-D5826C269BFE";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  1 10.393545264568585 60 3.2279573486586015
		 120 10.393545264568585;
createNode animCurveTA -name "ik_rotateY";
	rename -uuid "FBDE637D-4CB4-4AD5-1D1D-638424DDCBF6";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  1 -5.1731307424758439 60 -11.144719878678513
		 120 -5.1731307424758439;
createNode animCurveTA -name "ik_rotateZ";
	rename -uuid "A44CD031-4AE6-A17D-BDFF-07AB000ED896";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 3 ".keyTimeValue[0:2]"  1 -34.312537782070123 60 13.243042920759375
		 120 -34.312537782070123;
createNode mPyNode -name "gripNode1";
	rename -uuid "E4A307CE-45FE-53D7-03A9-E2A493200597";
	addAttr -readable false -cachedInternally true -shortName "inMatrix0" -longName "inMatrix0" 
		-attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "inMatrix1" -longName "inMatrix1" 
		-attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "parentInverseMatrix" 
		-longName "parentInverseMatrix" -attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "rotateOrder" -longName "rotateOrder" 
		-minValue 0 -maxValue 5 -attributeType "long";
	addAttr -readable false -cachedInternally true -keyable true -shortName "weight" 
		-longName "weight" -minValue 0 -maxValue 1 -attributeType "double";
	addAttr -readable false -cachedInternally true -keyable true -shortName "grip0" 
		-longName "grip0" -attributeType "long";
	addAttr -readable false -cachedInternally true -keyable true -shortName "grip1" 
		-longName "grip1" -attributeType "long";
	addAttr -writable false -storable false -shortName "outScale" -longName "outScale" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outScaleX" -longName "outScaleX" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outScaleY" -longName "outScaleY" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outScaleZ" -longName "outScaleZ" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outRotation" -longName "outRotation" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outRotationX" -longName "outRotationX" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outRotationY" -longName "outRotationY" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outRotationZ" -longName "outRotationZ" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outTranslation" -longName "outTranslation" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outTranslationX" -longName "outTranslationX" 
		-attributeType "double" -parent "outTranslation";
	addAttr -writable false -storable false -shortName "outTranslationY" -longName "outTranslationY" 
		-attributeType "double" -parent "outTranslation";
	addAttr -writable false -storable false -shortName "outTranslationZ" -longName "outTranslationZ" 
		-attributeType "double" -parent "outTranslation";
	addAttr -cachedInternally true -hidden true -shortName "type" -longName "type" -dataType "string";
	setAttr ".expression" -type "string" (
		"# Convert matrices to transformation matrices\ntarget_matrix0 = om.MTransformationMatrix(inMatrix0)\ntarget_matrix1 = om.MTransformationMatrix(inMatrix1)\n\n# Grab offsets from stored buffers\noffset_matrix0 = om.MTransformationMatrix(self.offsets[grip0])\noffset_matrix1 = om.MTransformationMatrix(self.offsets[grip1])\n\n# Extract components\ntarget_scale0 = target_matrix0.scale(om.MSpace.kWorld)             # scale0\ntarget_scale1 = target_matrix1.scale(om.MSpace.kWorld)             # scale1\ntarget_rotation0 = target_matrix0.rotation(asQuaternion=True)      # rotation0\ntarget_rotation1 = target_matrix1.rotation(asQuaternion=True)      # rotation1\ntarget_translation0 = target_matrix0.translation(om.MSpace.kWorld) # translation0\ntarget_translation1 = target_matrix1.translation(om.MSpace.kWorld) # translation1\n\noffset_scale0 = offset_matrix0.scale(om.MSpace.kWorld)             # scale0\noffset_scale1 = offset_matrix1.scale(om.MSpace.kWorld)             # scale1\noffset_rotation0 = offset_matrix0.rotation(asQuaternion=True)      # rotation0\n"
		+ "offset_rotation1 = offset_matrix1.rotation(asQuaternion=True)      # rotation1\noffset_translation0 = offset_matrix0.translation(om.MSpace.kWorld) # translation0\noffset_translation1 = offset_matrix1.translation(om.MSpace.kWorld) # translation1\n\n\n\n# Interpolate scale\nweight_ = 1-weight\ntarget_scale0[0] = target_scale1[0]**weight * target_scale0[0]**weight_\ntarget_scale0[1] = target_scale1[1]**weight * target_scale0[1]**weight_\ntarget_scale0[2] = target_scale1[2]**weight * target_scale0[2]**weight_\n\noffset_scale0[0] = offset_scale1[0]**weight * offset_scale0[0]**weight_\noffset_scale0[1] = offset_scale1[1]**weight * offset_scale0[1]**weight_\noffset_scale0[2] = offset_scale1[2]**weight * offset_scale0[2]**weight_\n\n\n# Interpolate rotation\ntarget_rotation0 = om.MQuaternion.slerp(target_rotation0,target_rotation1,weight)\noffset_rotation0 = om.MQuaternion.slerp(offset_rotation0,offset_rotation1,weight)\n\n\n# Interpolate translation\ntarget_translation0[0] = target_translation1[0]*weight + target_translation0[0]*weight_\ntarget_translation0[1] = target_translation1[1]*weight + target_translation0[1]*weight_\n"
		+ "target_translation0[2] = target_translation1[2]*weight + target_translation0[2]*weight_\n\noffset_translation0[0] = offset_translation1[0]*weight + offset_translation0[0]*weight_\noffset_translation0[1] = offset_translation1[1]*weight + offset_translation0[1]*weight_\noffset_translation0[2] = offset_translation1[2]*weight + offset_translation0[2]*weight_\n\n\n# Reconstruct a matrices with interpolated data\ntarget_matrix0.setScale(target_scale0,om.MSpace.kWorld)\ntarget_matrix0.setRotation(target_rotation0)\ntarget_matrix0.setTranslation(target_translation0, om.MSpace.kWorld)\n\noffset_matrix0.setScale(offset_scale0,om.MSpace.kWorld)\noffset_matrix0.setRotation(offset_rotation0)\noffset_matrix0.setTranslation(offset_translation0, om.MSpace.kWorld)\n\n\n# Apply offset\noutMatrix = om.MTransformationMatrix((offset_matrix0.asMatrix() * target_matrix0.asMatrix()) * parentInverseMatrix)\noutScale       = outMatrix.scale(om.MSpace.kTransform)\noutRotation    = outMatrix.rotation().reorder(rotateOrder)\noutTranslation = outMatrix.translation(om.MSpace.kTransform)\n"
		+ "\n");
	setAttr "._inputAttrs" -type "string" "gAJ9cQEoVQtyb3RhdGVPcmRlcl1xAlUDaW50cQNhVRNwYXJlbnRJbnZlcnNlTWF0cml4XXEEVQZt\nYXRyaXhxBWFVBndlaWdodF1xBlUFZmxvYXRxB2FVCWluTWF0cml4MV1xCFUGbWF0cml4cQlhVQlp\nbk1hdHJpeDBdcQpVBm1hdHJpeHELYVUFZ3JpcDFxDF1xDVUDaW50cQ5hVQVncmlwMF1xD1UDaW50\ncRBhdS4=\n";
	setAttr "._outputAttrs" -type "string" "gAJ9cQEoVQhvdXRTY2FsZV1xAlUGdmVjdG9ycQNhVQ5vdXRUcmFuc2xhdGlvbnEEXXEFVQZ2ZWN0\nb3JxBmFVC291dFJvdGF0aW9uXXEHVQVldWxlcnEIYXUu\n";
	setAttr "._storedVarNames" -type "string" "gAJdcQFVB29mZnNldHNxAmEu\n";
	setAttr "._storedVarsData" -type "string" "gAJ9cQFVB29mZnNldHNxAl1xA2NtcHlsaWIuYXBpLl9vcGVubWF5YQpNTWF0cml4CnEEKEc/8AAA\nAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAEcAAAAAAAAA\nAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcA\nAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAHSFUnEFYXMu\n";
	setAttr -lock on ".type" -type "string" "GripNode";
createNode mPyNode -name "gripNode2";
	rename -uuid "6E245A63-4393-19DC-4458-998AB1BD7D78";
	addAttr -readable false -cachedInternally true -shortName "inMatrix0" -longName "inMatrix0" 
		-attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "inMatrix1" -longName "inMatrix1" 
		-attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "parentInverseMatrix" 
		-longName "parentInverseMatrix" -attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "rotateOrder" -longName "rotateOrder" 
		-minValue 0 -maxValue 5 -attributeType "long";
	addAttr -readable false -cachedInternally true -keyable true -shortName "weight" 
		-longName "weight" -minValue 0 -maxValue 1 -attributeType "double";
	addAttr -readable false -cachedInternally true -keyable true -shortName "grip0" 
		-longName "grip0" -attributeType "long";
	addAttr -readable false -cachedInternally true -keyable true -shortName "grip1" 
		-longName "grip1" -attributeType "long";
	addAttr -writable false -storable false -shortName "outScale" -longName "outScale" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outScaleX" -longName "outScaleX" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outScaleY" -longName "outScaleY" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outScaleZ" -longName "outScaleZ" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outRotation" -longName "outRotation" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outRotationX" -longName "outRotationX" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outRotationY" -longName "outRotationY" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outRotationZ" -longName "outRotationZ" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outTranslation" -longName "outTranslation" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outTranslationX" -longName "outTranslationX" 
		-attributeType "double" -parent "outTranslation";
	addAttr -writable false -storable false -shortName "outTranslationY" -longName "outTranslationY" 
		-attributeType "double" -parent "outTranslation";
	addAttr -writable false -storable false -shortName "outTranslationZ" -longName "outTranslationZ" 
		-attributeType "double" -parent "outTranslation";
	addAttr -cachedInternally true -hidden true -shortName "type" -longName "type" -dataType "string";
	setAttr ".expression" -type "string" (
		"# Convert matrices to transformation matrices\ntarget_matrix0 = om.MTransformationMatrix(inMatrix0)\ntarget_matrix1 = om.MTransformationMatrix(inMatrix1)\n\n# Grab offsets from stored buffers\noffset_matrix0 = om.MTransformationMatrix(self.offsets[grip0])\noffset_matrix1 = om.MTransformationMatrix(self.offsets[grip1])\n\n# Extract components\ntarget_scale0 = target_matrix0.scale(om.MSpace.kWorld)             # scale0\ntarget_scale1 = target_matrix1.scale(om.MSpace.kWorld)             # scale1\ntarget_rotation0 = target_matrix0.rotation(asQuaternion=True)      # rotation0\ntarget_rotation1 = target_matrix1.rotation(asQuaternion=True)      # rotation1\ntarget_translation0 = target_matrix0.translation(om.MSpace.kWorld) # translation0\ntarget_translation1 = target_matrix1.translation(om.MSpace.kWorld) # translation1\n\noffset_scale0 = offset_matrix0.scale(om.MSpace.kWorld)             # scale0\noffset_scale1 = offset_matrix1.scale(om.MSpace.kWorld)             # scale1\noffset_rotation0 = offset_matrix0.rotation(asQuaternion=True)      # rotation0\n"
		+ "offset_rotation1 = offset_matrix1.rotation(asQuaternion=True)      # rotation1\noffset_translation0 = offset_matrix0.translation(om.MSpace.kWorld) # translation0\noffset_translation1 = offset_matrix1.translation(om.MSpace.kWorld) # translation1\n\n\n\n# Interpolate scale\nweight_ = 1-weight\ntarget_scale0[0] = target_scale1[0]**weight * target_scale0[0]**weight_\ntarget_scale0[1] = target_scale1[1]**weight * target_scale0[1]**weight_\ntarget_scale0[2] = target_scale1[2]**weight * target_scale0[2]**weight_\n\noffset_scale0[0] = offset_scale1[0]**weight * offset_scale0[0]**weight_\noffset_scale0[1] = offset_scale1[1]**weight * offset_scale0[1]**weight_\noffset_scale0[2] = offset_scale1[2]**weight * offset_scale0[2]**weight_\n\n\n# Interpolate rotation\ntarget_rotation0 = om.MQuaternion.slerp(target_rotation0,target_rotation1,weight)\noffset_rotation0 = om.MQuaternion.slerp(offset_rotation0,offset_rotation1,weight)\n\n\n# Interpolate translation\ntarget_translation0[0] = target_translation1[0]*weight + target_translation0[0]*weight_\ntarget_translation0[1] = target_translation1[1]*weight + target_translation0[1]*weight_\n"
		+ "target_translation0[2] = target_translation1[2]*weight + target_translation0[2]*weight_\n\noffset_translation0[0] = offset_translation1[0]*weight + offset_translation0[0]*weight_\noffset_translation0[1] = offset_translation1[1]*weight + offset_translation0[1]*weight_\noffset_translation0[2] = offset_translation1[2]*weight + offset_translation0[2]*weight_\n\n\n# Reconstruct a matrices with interpolated data\ntarget_matrix0.setScale(target_scale0,om.MSpace.kWorld)\ntarget_matrix0.setRotation(target_rotation0)\ntarget_matrix0.setTranslation(target_translation0, om.MSpace.kWorld)\n\noffset_matrix0.setScale(offset_scale0,om.MSpace.kWorld)\noffset_matrix0.setRotation(offset_rotation0)\noffset_matrix0.setTranslation(offset_translation0, om.MSpace.kWorld)\n\n\n# Apply offset\noutMatrix = om.MTransformationMatrix((offset_matrix0.asMatrix() * target_matrix0.asMatrix()) * parentInverseMatrix)\noutScale       = outMatrix.scale(om.MSpace.kTransform)\noutRotation    = outMatrix.rotation().reorder(rotateOrder)\noutTranslation = outMatrix.translation(om.MSpace.kTransform)\n"
		+ "\n");
	setAttr "._inputAttrs" -type "string" "gAJ9cQEoVQtyb3RhdGVPcmRlcl1xAlUDaW50cQNhVRNwYXJlbnRJbnZlcnNlTWF0cml4XXEEVQZt\nYXRyaXhxBWFVBndlaWdodF1xBlUFZmxvYXRxB2FVCWluTWF0cml4MV1xCFUGbWF0cml4cQlhVQlp\nbk1hdHJpeDBdcQpVBm1hdHJpeHELYVUFZ3JpcDFxDF1xDVUDaW50cQ5hVQVncmlwMF1xD1UDaW50\ncRBhdS4=\n";
	setAttr "._outputAttrs" -type "string" "gAJ9cQEoVQhvdXRTY2FsZV1xAlUGdmVjdG9ycQNhVQ5vdXRUcmFuc2xhdGlvbnEEXXEFVQZ2ZWN0\nb3JxBmFVC291dFJvdGF0aW9uXXEHVQVldWxlcnEIYXUu\n";
	setAttr "._storedVarNames" -type "string" "gAJdcQFVB29mZnNldHNxAmEu\n";
	setAttr "._storedVarsData" -type "string" "gAJ9cQFVB29mZnNldHNxAl1xA2NtcHlsaWIuYXBpLl9vcGVubWF5YQpNTWF0cml4CnEEKEc/8AAA\nAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAEcAAAAAAAAA\nAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcA\nAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAHSFUnEFYXMu\n";
	setAttr -lock on ".type" -type "string" "GripNode";
createNode mPyNode -name "gripNode3";
	rename -uuid "8EF36D70-48DB-D700-40F9-14840F510A07";
	addAttr -readable false -cachedInternally true -shortName "inMatrix0" -longName "inMatrix0" 
		-attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "inMatrix1" -longName "inMatrix1" 
		-attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "parentInverseMatrix" 
		-longName "parentInverseMatrix" -attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "rotateOrder" -longName "rotateOrder" 
		-minValue 0 -maxValue 5 -attributeType "long";
	addAttr -readable false -cachedInternally true -keyable true -shortName "weight" 
		-longName "weight" -minValue 0 -maxValue 1 -attributeType "double";
	addAttr -readable false -cachedInternally true -keyable true -shortName "grip0" 
		-longName "grip0" -attributeType "long";
	addAttr -readable false -cachedInternally true -keyable true -shortName "grip1" 
		-longName "grip1" -attributeType "long";
	addAttr -writable false -storable false -shortName "outScale" -longName "outScale" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outScaleX" -longName "outScaleX" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outScaleY" -longName "outScaleY" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outScaleZ" -longName "outScaleZ" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outRotation" -longName "outRotation" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outRotationX" -longName "outRotationX" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outRotationY" -longName "outRotationY" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outRotationZ" -longName "outRotationZ" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outTranslation" -longName "outTranslation" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outTranslationX" -longName "outTranslationX" 
		-attributeType "double" -parent "outTranslation";
	addAttr -writable false -storable false -shortName "outTranslationY" -longName "outTranslationY" 
		-attributeType "double" -parent "outTranslation";
	addAttr -writable false -storable false -shortName "outTranslationZ" -longName "outTranslationZ" 
		-attributeType "double" -parent "outTranslation";
	addAttr -cachedInternally true -hidden true -shortName "type" -longName "type" -dataType "string";
	setAttr ".expression" -type "string" (
		"# Convert matrices to transformation matrices\ntarget_matrix0 = om.MTransformationMatrix(inMatrix0)\ntarget_matrix1 = om.MTransformationMatrix(inMatrix1)\n\n# Grab offsets from stored buffers\noffset_matrix0 = om.MTransformationMatrix(self.offsets[grip0])\noffset_matrix1 = om.MTransformationMatrix(self.offsets[grip1])\n\n# Extract components\ntarget_scale0 = target_matrix0.scale(om.MSpace.kWorld)             # scale0\ntarget_scale1 = target_matrix1.scale(om.MSpace.kWorld)             # scale1\ntarget_rotation0 = target_matrix0.rotation(asQuaternion=True)      # rotation0\ntarget_rotation1 = target_matrix1.rotation(asQuaternion=True)      # rotation1\ntarget_translation0 = target_matrix0.translation(om.MSpace.kWorld) # translation0\ntarget_translation1 = target_matrix1.translation(om.MSpace.kWorld) # translation1\n\noffset_scale0 = offset_matrix0.scale(om.MSpace.kWorld)             # scale0\noffset_scale1 = offset_matrix1.scale(om.MSpace.kWorld)             # scale1\noffset_rotation0 = offset_matrix0.rotation(asQuaternion=True)      # rotation0\n"
		+ "offset_rotation1 = offset_matrix1.rotation(asQuaternion=True)      # rotation1\noffset_translation0 = offset_matrix0.translation(om.MSpace.kWorld) # translation0\noffset_translation1 = offset_matrix1.translation(om.MSpace.kWorld) # translation1\n\n\n\n# Interpolate scale\nweight_ = 1-weight\ntarget_scale0[0] = target_scale1[0]**weight * target_scale0[0]**weight_\ntarget_scale0[1] = target_scale1[1]**weight * target_scale0[1]**weight_\ntarget_scale0[2] = target_scale1[2]**weight * target_scale0[2]**weight_\n\noffset_scale0[0] = offset_scale1[0]**weight * offset_scale0[0]**weight_\noffset_scale0[1] = offset_scale1[1]**weight * offset_scale0[1]**weight_\noffset_scale0[2] = offset_scale1[2]**weight * offset_scale0[2]**weight_\n\n\n# Interpolate rotation\ntarget_rotation0 = om.MQuaternion.slerp(target_rotation0,target_rotation1,weight)\noffset_rotation0 = om.MQuaternion.slerp(offset_rotation0,offset_rotation1,weight)\n\n\n# Interpolate translation\ntarget_translation0[0] = target_translation1[0]*weight + target_translation0[0]*weight_\ntarget_translation0[1] = target_translation1[1]*weight + target_translation0[1]*weight_\n"
		+ "target_translation0[2] = target_translation1[2]*weight + target_translation0[2]*weight_\n\noffset_translation0[0] = offset_translation1[0]*weight + offset_translation0[0]*weight_\noffset_translation0[1] = offset_translation1[1]*weight + offset_translation0[1]*weight_\noffset_translation0[2] = offset_translation1[2]*weight + offset_translation0[2]*weight_\n\n\n# Reconstruct a matrices with interpolated data\ntarget_matrix0.setScale(target_scale0,om.MSpace.kWorld)\ntarget_matrix0.setRotation(target_rotation0)\ntarget_matrix0.setTranslation(target_translation0, om.MSpace.kWorld)\n\noffset_matrix0.setScale(offset_scale0,om.MSpace.kWorld)\noffset_matrix0.setRotation(offset_rotation0)\noffset_matrix0.setTranslation(offset_translation0, om.MSpace.kWorld)\n\n\n# Apply offset\noutMatrix = om.MTransformationMatrix((offset_matrix0.asMatrix() * target_matrix0.asMatrix()) * parentInverseMatrix)\noutScale       = outMatrix.scale(om.MSpace.kTransform)\noutRotation    = outMatrix.rotation().reorder(rotateOrder)\noutTranslation = outMatrix.translation(om.MSpace.kTransform)\n"
		+ "\n");
	setAttr "._inputAttrs" -type "string" "gAJ9cQEoVQtyb3RhdGVPcmRlcl1xAlUDaW50cQNhVRNwYXJlbnRJbnZlcnNlTWF0cml4XXEEVQZt\nYXRyaXhxBWFVBndlaWdodF1xBlUFZmxvYXRxB2FVCWluTWF0cml4MV1xCFUGbWF0cml4cQlhVQlp\nbk1hdHJpeDBdcQpVBm1hdHJpeHELYVUFZ3JpcDFxDF1xDVUDaW50cQ5hVQVncmlwMF1xD1UDaW50\ncRBhdS4=\n";
	setAttr "._outputAttrs" -type "string" "gAJ9cQEoVQhvdXRTY2FsZV1xAlUGdmVjdG9ycQNhVQ5vdXRUcmFuc2xhdGlvbnEEXXEFVQZ2ZWN0\nb3JxBmFVC291dFJvdGF0aW9uXXEHVQVldWxlcnEIYXUu\n";
	setAttr "._storedVarNames" -type "string" "gAJdcQFVB29mZnNldHNxAmEu\n";
	setAttr "._storedVarsData" -type "string" "gAJ9cQFVB29mZnNldHNxAl1xA2NtcHlsaWIuYXBpLl9vcGVubWF5YQpNTWF0cml4CnEEKEc/8AAA\nAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAEcAAAAAAAAA\nAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcA\nAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAHSFUnEFYXMu\n";
	setAttr -lock on ".type" -type "string" "GripNode";
createNode mPyNode -name "gripNode4";
	rename -uuid "DFDBCCC4-4D87-C176-2CCA-BD9C2323A875";
	addAttr -readable false -cachedInternally true -shortName "inMatrix0" -longName "inMatrix0" 
		-attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "inMatrix1" -longName "inMatrix1" 
		-attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "parentInverseMatrix" 
		-longName "parentInverseMatrix" -attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "rotateOrder" -longName "rotateOrder" 
		-minValue 0 -maxValue 5 -attributeType "long";
	addAttr -readable false -cachedInternally true -keyable true -shortName "weight" 
		-longName "weight" -minValue 0 -maxValue 1 -attributeType "double";
	addAttr -readable false -cachedInternally true -keyable true -shortName "grip0" 
		-longName "grip0" -attributeType "long";
	addAttr -readable false -cachedInternally true -keyable true -shortName "grip1" 
		-longName "grip1" -attributeType "long";
	addAttr -writable false -storable false -shortName "outScale" -longName "outScale" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outScaleX" -longName "outScaleX" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outScaleY" -longName "outScaleY" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outScaleZ" -longName "outScaleZ" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outRotation" -longName "outRotation" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outRotationX" -longName "outRotationX" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outRotationY" -longName "outRotationY" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outRotationZ" -longName "outRotationZ" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outTranslation" -longName "outTranslation" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outTranslationX" -longName "outTranslationX" 
		-attributeType "double" -parent "outTranslation";
	addAttr -writable false -storable false -shortName "outTranslationY" -longName "outTranslationY" 
		-attributeType "double" -parent "outTranslation";
	addAttr -writable false -storable false -shortName "outTranslationZ" -longName "outTranslationZ" 
		-attributeType "double" -parent "outTranslation";
	addAttr -cachedInternally true -hidden true -shortName "type" -longName "type" -dataType "string";
	setAttr ".expression" -type "string" (
		"# Convert matrices to transformation matrices\ntarget_matrix0 = om.MTransformationMatrix(inMatrix0)\ntarget_matrix1 = om.MTransformationMatrix(inMatrix1)\n\n# Grab offsets from stored buffers\noffset_matrix0 = om.MTransformationMatrix(self.offsets[grip0])\noffset_matrix1 = om.MTransformationMatrix(self.offsets[grip1])\n\n# Extract components\ntarget_scale0 = target_matrix0.scale(om.MSpace.kWorld)             # scale0\ntarget_scale1 = target_matrix1.scale(om.MSpace.kWorld)             # scale1\ntarget_rotation0 = target_matrix0.rotation(asQuaternion=True)      # rotation0\ntarget_rotation1 = target_matrix1.rotation(asQuaternion=True)      # rotation1\ntarget_translation0 = target_matrix0.translation(om.MSpace.kWorld) # translation0\ntarget_translation1 = target_matrix1.translation(om.MSpace.kWorld) # translation1\n\noffset_scale0 = offset_matrix0.scale(om.MSpace.kWorld)             # scale0\noffset_scale1 = offset_matrix1.scale(om.MSpace.kWorld)             # scale1\noffset_rotation0 = offset_matrix0.rotation(asQuaternion=True)      # rotation0\n"
		+ "offset_rotation1 = offset_matrix1.rotation(asQuaternion=True)      # rotation1\noffset_translation0 = offset_matrix0.translation(om.MSpace.kWorld) # translation0\noffset_translation1 = offset_matrix1.translation(om.MSpace.kWorld) # translation1\n\n\n\n# Interpolate scale\nweight_ = 1-weight\ntarget_scale0[0] = target_scale1[0]**weight * target_scale0[0]**weight_\ntarget_scale0[1] = target_scale1[1]**weight * target_scale0[1]**weight_\ntarget_scale0[2] = target_scale1[2]**weight * target_scale0[2]**weight_\n\noffset_scale0[0] = offset_scale1[0]**weight * offset_scale0[0]**weight_\noffset_scale0[1] = offset_scale1[1]**weight * offset_scale0[1]**weight_\noffset_scale0[2] = offset_scale1[2]**weight * offset_scale0[2]**weight_\n\n\n# Interpolate rotation\ntarget_rotation0 = om.MQuaternion.slerp(target_rotation0,target_rotation1,weight)\noffset_rotation0 = om.MQuaternion.slerp(offset_rotation0,offset_rotation1,weight)\n\n\n# Interpolate translation\ntarget_translation0[0] = target_translation1[0]*weight + target_translation0[0]*weight_\ntarget_translation0[1] = target_translation1[1]*weight + target_translation0[1]*weight_\n"
		+ "target_translation0[2] = target_translation1[2]*weight + target_translation0[2]*weight_\n\noffset_translation0[0] = offset_translation1[0]*weight + offset_translation0[0]*weight_\noffset_translation0[1] = offset_translation1[1]*weight + offset_translation0[1]*weight_\noffset_translation0[2] = offset_translation1[2]*weight + offset_translation0[2]*weight_\n\n\n# Reconstruct a matrices with interpolated data\ntarget_matrix0.setScale(target_scale0,om.MSpace.kWorld)\ntarget_matrix0.setRotation(target_rotation0)\ntarget_matrix0.setTranslation(target_translation0, om.MSpace.kWorld)\n\noffset_matrix0.setScale(offset_scale0,om.MSpace.kWorld)\noffset_matrix0.setRotation(offset_rotation0)\noffset_matrix0.setTranslation(offset_translation0, om.MSpace.kWorld)\n\n\n# Apply offset\noutMatrix = om.MTransformationMatrix((offset_matrix0.asMatrix() * target_matrix0.asMatrix()) * parentInverseMatrix)\noutScale       = outMatrix.scale(om.MSpace.kTransform)\noutRotation    = outMatrix.rotation().reorder(rotateOrder)\noutTranslation = outMatrix.translation(om.MSpace.kTransform)\n"
		+ "\n");
	setAttr "._inputAttrs" -type "string" "gAJ9cQEoVQtyb3RhdGVPcmRlcl1xAlUDaW50cQNhVRNwYXJlbnRJbnZlcnNlTWF0cml4XXEEVQZt\nYXRyaXhxBWFVBndlaWdodF1xBlUFZmxvYXRxB2FVCWluTWF0cml4MV1xCFUGbWF0cml4cQlhVQlp\nbk1hdHJpeDBdcQpVBm1hdHJpeHELYVUFZ3JpcDFxDF1xDVUDaW50cQ5hVQVncmlwMF1xD1UDaW50\ncRBhdS4=\n";
	setAttr "._outputAttrs" -type "string" "gAJ9cQEoVQhvdXRTY2FsZV1xAlUGdmVjdG9ycQNhVQ5vdXRUcmFuc2xhdGlvbnEEXXEFVQZ2ZWN0\nb3JxBmFVC291dFJvdGF0aW9uXXEHVQVldWxlcnEIYXUu\n";
	setAttr "._storedVarNames" -type "string" "gAJdcQFVB29mZnNldHNxAmEu\n";
	setAttr "._storedVarsData" -type "string" "gAJ9cQFVB29mZnNldHNxAl1xA2NtcHlsaWIuYXBpLl9vcGVubWF5YQpNTWF0cml4CnEEKEc/8AAA\nAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAEcAAAAAAAAA\nAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcA\nAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAHSFUnEFYXMu\n";
	setAttr -lock on ".type" -type "string" "GripNode";
createNode mPyNode -name "gripNode5";
	rename -uuid "9D4791B8-4225-E116-5F1B-8AA3FFDF34C2";
	addAttr -readable false -cachedInternally true -shortName "inMatrix0" -longName "inMatrix0" 
		-attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "inMatrix1" -longName "inMatrix1" 
		-attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "parentInverseMatrix" 
		-longName "parentInverseMatrix" -attributeType "matrix";
	addAttr -readable false -cachedInternally true -shortName "rotateOrder" -longName "rotateOrder" 
		-minValue 0 -maxValue 5 -attributeType "long";
	addAttr -readable false -cachedInternally true -keyable true -shortName "weight" 
		-longName "weight" -minValue 0 -maxValue 1 -attributeType "double";
	addAttr -readable false -cachedInternally true -keyable true -shortName "grip0" 
		-longName "grip0" -attributeType "long";
	addAttr -readable false -cachedInternally true -keyable true -shortName "grip1" 
		-longName "grip1" -attributeType "long";
	addAttr -writable false -storable false -shortName "outScale" -longName "outScale" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outScaleX" -longName "outScaleX" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outScaleY" -longName "outScaleY" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outScaleZ" -longName "outScaleZ" 
		-attributeType "double" -parent "outScale";
	addAttr -writable false -storable false -shortName "outRotation" -longName "outRotation" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outRotationX" -longName "outRotationX" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outRotationY" -longName "outRotationY" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outRotationZ" -longName "outRotationZ" 
		-attributeType "doubleAngle" -parent "outRotation";
	addAttr -writable false -storable false -shortName "outTranslation" -longName "outTranslation" 
		-attributeType "double3" -numberOfChildren 3;
	addAttr -writable false -storable false -shortName "outTranslationX" -longName "outTranslationX" 
		-attributeType "double" -parent "outTranslation";
	addAttr -writable false -storable false -shortName "outTranslationY" -longName "outTranslationY" 
		-attributeType "double" -parent "outTranslation";
	addAttr -writable false -storable false -shortName "outTranslationZ" -longName "outTranslationZ" 
		-attributeType "double" -parent "outTranslation";
	addAttr -cachedInternally true -hidden true -shortName "type" -longName "type" -dataType "string";
	setAttr ".expression" -type "string" (
		"# Convert matrices to transformation matrices\ntarget_matrix0 = om.MTransformationMatrix(inMatrix0)\ntarget_matrix1 = om.MTransformationMatrix(inMatrix1)\n\n# Grab offsets from stored buffers\noffset_matrix0 = om.MTransformationMatrix(self.offsets[grip0])\noffset_matrix1 = om.MTransformationMatrix(self.offsets[grip1])\n\n# Extract components\ntarget_scale0 = target_matrix0.scale(om.MSpace.kWorld)             # scale0\ntarget_scale1 = target_matrix1.scale(om.MSpace.kWorld)             # scale1\ntarget_rotation0 = target_matrix0.rotation(asQuaternion=True)      # rotation0\ntarget_rotation1 = target_matrix1.rotation(asQuaternion=True)      # rotation1\ntarget_translation0 = target_matrix0.translation(om.MSpace.kWorld) # translation0\ntarget_translation1 = target_matrix1.translation(om.MSpace.kWorld) # translation1\n\noffset_scale0 = offset_matrix0.scale(om.MSpace.kWorld)             # scale0\noffset_scale1 = offset_matrix1.scale(om.MSpace.kWorld)             # scale1\noffset_rotation0 = offset_matrix0.rotation(asQuaternion=True)      # rotation0\n"
		+ "offset_rotation1 = offset_matrix1.rotation(asQuaternion=True)      # rotation1\noffset_translation0 = offset_matrix0.translation(om.MSpace.kWorld) # translation0\noffset_translation1 = offset_matrix1.translation(om.MSpace.kWorld) # translation1\n\n\n\n# Interpolate scale\nweight_ = 1-weight\ntarget_scale0[0] = target_scale1[0]**weight * target_scale0[0]**weight_\ntarget_scale0[1] = target_scale1[1]**weight * target_scale0[1]**weight_\ntarget_scale0[2] = target_scale1[2]**weight * target_scale0[2]**weight_\n\noffset_scale0[0] = offset_scale1[0]**weight * offset_scale0[0]**weight_\noffset_scale0[1] = offset_scale1[1]**weight * offset_scale0[1]**weight_\noffset_scale0[2] = offset_scale1[2]**weight * offset_scale0[2]**weight_\n\n\n# Interpolate rotation\ntarget_rotation0 = om.MQuaternion.slerp(target_rotation0,target_rotation1,weight)\noffset_rotation0 = om.MQuaternion.slerp(offset_rotation0,offset_rotation1,weight)\n\n\n# Interpolate translation\ntarget_translation0[0] = target_translation1[0]*weight + target_translation0[0]*weight_\ntarget_translation0[1] = target_translation1[1]*weight + target_translation0[1]*weight_\n"
		+ "target_translation0[2] = target_translation1[2]*weight + target_translation0[2]*weight_\n\noffset_translation0[0] = offset_translation1[0]*weight + offset_translation0[0]*weight_\noffset_translation0[1] = offset_translation1[1]*weight + offset_translation0[1]*weight_\noffset_translation0[2] = offset_translation1[2]*weight + offset_translation0[2]*weight_\n\n\n# Reconstruct a matrices with interpolated data\ntarget_matrix0.setScale(target_scale0,om.MSpace.kWorld)\ntarget_matrix0.setRotation(target_rotation0)\ntarget_matrix0.setTranslation(target_translation0, om.MSpace.kWorld)\n\noffset_matrix0.setScale(offset_scale0,om.MSpace.kWorld)\noffset_matrix0.setRotation(offset_rotation0)\noffset_matrix0.setTranslation(offset_translation0, om.MSpace.kWorld)\n\n\n# Apply offset\noutMatrix = om.MTransformationMatrix((offset_matrix0.asMatrix() * target_matrix0.asMatrix()) * parentInverseMatrix)\noutScale       = outMatrix.scale(om.MSpace.kTransform)\noutRotation    = outMatrix.rotation().reorder(rotateOrder)\noutTranslation = outMatrix.translation(om.MSpace.kTransform)\n"
		+ "\n");
	setAttr "._inputAttrs" -type "string" "gAJ9cQEoVQtyb3RhdGVPcmRlcl1xAlUDaW50cQNhVRNwYXJlbnRJbnZlcnNlTWF0cml4XXEEVQZt\nYXRyaXhxBWFVBndlaWdodF1xBlUFZmxvYXRxB2FVCWluTWF0cml4MV1xCFUGbWF0cml4cQlhVQlp\nbk1hdHJpeDBdcQpVBm1hdHJpeHELYVUFZ3JpcDFxDF1xDVUDaW50cQ5hVQVncmlwMF1xD1UDaW50\ncRBhdS4=\n";
	setAttr "._outputAttrs" -type "string" "gAJ9cQEoVQhvdXRTY2FsZV1xAlUGdmVjdG9ycQNhVQ5vdXRUcmFuc2xhdGlvbnEEXXEFVQZ2ZWN0\nb3JxBmFVC291dFJvdGF0aW9uXXEHVQVldWxlcnEIYXUu\n";
	setAttr "._storedVarNames" -type "string" "gAJdcQFVB29mZnNldHNxAmEu\n";
	setAttr "._storedVarsData" -type "string" "gAJ9cQFVB29mZnNldHNxAl1xAyhjbXB5bGliLmFwaS5fb3Blbm1heWEKTU1hdHJpeApxBChHP+//\n//////1HAAAAAAAAAABHAAAAAAAAAABHAAAAAAAAAABHAAAAAAAAAABHP+////////1HAAAAAAAA\nAABHAAAAAAAAAABHAAAAAAAAAABHAAAAAAAAAABHP/AAAAAAAABHAAAAAAAAAABHPOAAAAAAAABH\nQBsZlF4F6BhHPM5AAAAAAABHP/AAAAAAAAB0hVJxBWgEKEc/8AAAAAAAAEcAAAAAAAAAAEcAAAAA\nAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEc/8AAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAA\nAEcAAAAAAAAAAEc/8AAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEcAAAAAAAAAAEc/\n8AAAAAAAAHSFUnEGaAQoRz/qUtNzOp+nRz/hUAx6/pTKR7/GZMIb6lKaRwAAAAAAAAAAR7/h9xOY\n0gWHRz/qSnrjx3owR7+5WVzg29IDRwAAAAAAAAAARz+3FRbLmoo9Rz/G/4qKfC+rRz/vWMOJocTn\nRwAAAAAAAAAAR8Am9jvxr/GXR8AQy0JFeS6gRz/8kq/rbubwRz/wAAAAAAAAdIVScQdlcy4=\n";
	setAttr -keyable on ".weight";
	setAttr -keyable on ".grip0";
	setAttr -keyable on ".grip1";
	setAttr -lock on ".type" -type "string" "GripNode";
createNode choice -name "gripNode5_inMatrix0";
	rename -uuid "04E16F66-48D2-E7B7-B271-4F9DC1B5F2F8";
	setAttr -size 3 ".input";
createNode choice -name "gripNode5_inMatrix1";
	rename -uuid "A7D2C947-444B-D334-FA10-3FB1608D812A";
	setAttr -size 3 ".input";
createNode animCurveTU -name "pCube1_blend";
	rename -uuid "735EFEA8-4050-7B51-AEE5-1F9FAE014E18";
	setAttr ".tangentType" 18;
	setAttr ".weightedTangents" no;
	setAttr -size 2 ".keyTimeValue[0:1]"  1 0 45 1;
createNode script -name "uiConfigurationScriptNode";
	rename -uuid "A1796E13-4F42-EDA8-CAAB-838A87D00D72";
	setAttr ".before" -type "string" (
		"// Maya Mel UI Configuration File.\n//\n//  This script is machine generated.  Edit at your own risk.\n//\n//\n\nglobal string $gMainPane;\nif (`paneLayout -exists $gMainPane`) {\n\n\tglobal int $gUseScenePanelConfig;\n\tint    $useSceneConfig = $gUseScenePanelConfig;\n\tint    $nodeEditorPanelVisible = stringArrayContains(\"nodeEditorPanel1\", `getPanel -vis`);\n\tint    $nodeEditorWorkspaceControlOpen = (`workspaceControl -exists nodeEditorPanel1Window` && `workspaceControl -q -visible nodeEditorPanel1Window`);\n\tint    $menusOkayInPanels = `optionVar -q allowMenusInPanels`;\n\tint    $nVisPanes = `paneLayout -q -nvp $gMainPane`;\n\tint    $nPanes = 0;\n\tstring $editorName;\n\tstring $panelName;\n\tstring $itemFilterName;\n\tstring $panelConfig;\n\n\t//\n\t//  get current state of the UI\n\t//\n\tsceneUIReplacement -update $gMainPane;\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Top View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Top View\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"top\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 32768\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n"
		+ "            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n"
		+ "            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 1\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 686\n            -height 605\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n"
		+ "\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Side View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Side View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"side\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n"
		+ "            -textureDisplay \"modulate\" \n            -textureMaxSize 32768\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n"
		+ "            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 1\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 685\n            -height 605\n"
		+ "            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Front View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Front View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"front\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n"
		+ "            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 32768\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n"
		+ "            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n"
		+ "            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 1\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 686\n            -height 605\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"modelPanel\" (localizedPanelLabel(\"Persp View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tmodelPanel -edit -l (localizedPanelLabel(\"Persp View\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        modelEditor -e \n            -camera \"persp\" \n            -useInteractiveMode 0\n            -displayLights \"default\" \n            -displayAppearance \"smoothShaded\" \n            -activeOnly 0\n            -ignorePanZoom 0\n"
		+ "            -wireframeOnShaded 0\n            -headsUpDisplay 1\n            -holdOuts 1\n            -selectionHiliteDisplay 1\n            -useDefaultMaterial 0\n            -bufferMode \"double\" \n            -twoSidedLighting 0\n            -backfaceCulling 0\n            -xray 0\n            -jointXray 0\n            -activeComponentsXray 0\n            -displayTextures 0\n            -smoothWireframe 0\n            -lineWidth 1\n            -textureAnisotropic 0\n            -textureHilight 1\n            -textureSampling 2\n            -textureDisplay \"modulate\" \n            -textureMaxSize 32768\n            -fogging 0\n            -fogSource \"fragment\" \n            -fogMode \"linear\" \n            -fogStart 0\n            -fogEnd 100\n            -fogDensity 0.1\n            -fogColor 0.5 0.5 0.5 1 \n            -depthOfFieldPreview 1\n            -maxConstantTransparency 1\n            -rendererName \"vp2Renderer\" \n            -objectFilterShowInHUD 1\n            -isFiltered 0\n            -colorResolution 256 256 \n            -bumpResolution 512 512 \n"
		+ "            -textureCompression 0\n            -transparencyAlgorithm \"frontAndBackCull\" \n            -transpInShadows 0\n            -cullingOverride \"none\" \n            -lowQualityLighting 0\n            -maximumNumHardwareLights 1\n            -occlusionCulling 0\n            -shadingModel 0\n            -useBaseRenderer 0\n            -useReducedRenderer 0\n            -smallObjectCulling 0\n            -smallObjectThreshold -1 \n            -interactiveDisableShadows 0\n            -interactiveBackFaceCull 0\n            -sortTransparent 1\n            -controllers 1\n            -nurbsCurves 1\n            -nurbsSurfaces 1\n            -polymeshes 1\n            -subdivSurfaces 1\n            -planes 1\n            -lights 1\n            -cameras 1\n            -controlVertices 1\n            -hulls 1\n            -grid 1\n            -imagePlane 1\n            -joints 1\n            -ikHandles 1\n            -deformers 1\n            -dynamics 1\n            -particleInstancers 1\n            -fluids 1\n            -hairSystems 1\n            -follicles 1\n"
		+ "            -nCloths 1\n            -nParticles 1\n            -nRigids 1\n            -dynamicConstraints 1\n            -locators 1\n            -manipulators 1\n            -pluginShapes 1\n            -dimensions 1\n            -handles 1\n            -pivots 1\n            -textures 1\n            -strokes 1\n            -motionTrails 1\n            -clipGhosts 1\n            -greasePencils 1\n            -shadows 0\n            -captureSequenceNumber -1\n            -width 685\n            -height 605\n            -sceneRenderFilter 0\n            $editorName;\n        modelEditor -e -viewSelected 0 $editorName;\n        modelEditor -e \n            -pluginObjects \"gpuCacheDisplayFilter\" 1 \n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"outlinerPanel\" (localizedPanelLabel(\"ToggledOutliner\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\toutlinerPanel -edit -l (localizedPanelLabel(\"ToggledOutliner\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\t$editorName = $panelName;\n        outlinerEditor -e \n            -showShapes 0\n            -showAssignedMaterials 0\n            -showTimeEditor 1\n            -showReferenceNodes 1\n            -showReferenceMembers 1\n            -showAttributes 0\n            -showConnected 0\n            -showAnimCurvesOnly 0\n            -showMuteInfo 0\n            -organizeByLayer 1\n            -organizeByClip 1\n            -showAnimLayerWeight 1\n            -autoExpandLayers 1\n            -autoExpand 0\n            -showDagOnly 1\n            -showAssets 1\n            -showContainedOnly 1\n            -showPublishedAsConnected 0\n            -showParentContainers 0\n            -showContainerContents 1\n            -ignoreDagHierarchy 0\n            -expandConnections 0\n            -showUpstreamCurves 1\n            -showUnitlessCurves 1\n            -showCompounds 1\n            -showLeafs 1\n            -showNumericAttrsOnly 0\n            -highlightActive 1\n            -autoSelectNewObjects 0\n            -doNotSelectNewObjects 0\n            -dropIsParent 1\n"
		+ "            -transmitFilters 0\n            -setFilter \"defaultSetFilter\" \n            -showSetMembers 1\n            -allowMultiSelection 1\n            -alwaysToggleSelect 0\n            -directSelect 0\n            -isSet 0\n            -isSetMember 0\n            -displayMode \"DAG\" \n            -expandObjects 0\n            -setsIgnoreFilters 1\n            -containersIgnoreFilters 0\n            -editAttrName 0\n            -showAttrValues 0\n            -highlightSecondary 0\n            -showUVAttrsOnly 0\n            -showTextureNodesOnly 0\n            -attrAlphaOrder \"default\" \n            -animLayerFilterOptions \"allAffecting\" \n            -sortOrder \"none\" \n            -longNames 0\n            -niceNames 1\n            -showNamespace 1\n            -showPinIcons 0\n            -mapMotionTrails 0\n            -ignoreHiddenAttribute 0\n            -ignoreOutlinerColor 0\n            -renderFilterVisible 0\n            -renderFilterIndex 0\n            -selectionOrder \"chronological\" \n            -expandAttribute 0\n            $editorName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"outlinerPanel\" (localizedPanelLabel(\"Outliner\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\toutlinerPanel -edit -l (localizedPanelLabel(\"Outliner\")) -mbv $menusOkayInPanels  $panelName;\n\t\t$editorName = $panelName;\n        outlinerEditor -e \n            -showShapes 0\n            -showAssignedMaterials 0\n            -showTimeEditor 1\n            -showReferenceNodes 0\n            -showReferenceMembers 0\n            -showAttributes 0\n            -showConnected 0\n            -showAnimCurvesOnly 0\n            -showMuteInfo 0\n            -organizeByLayer 1\n            -organizeByClip 1\n            -showAnimLayerWeight 1\n            -autoExpandLayers 1\n            -autoExpand 0\n            -showDagOnly 1\n            -showAssets 1\n            -showContainedOnly 1\n            -showPublishedAsConnected 0\n            -showParentContainers 0\n            -showContainerContents 1\n            -ignoreDagHierarchy 0\n"
		+ "            -expandConnections 0\n            -showUpstreamCurves 1\n            -showUnitlessCurves 1\n            -showCompounds 1\n            -showLeafs 1\n            -showNumericAttrsOnly 0\n            -highlightActive 1\n            -autoSelectNewObjects 0\n            -doNotSelectNewObjects 0\n            -dropIsParent 1\n            -transmitFilters 0\n            -setFilter \"0\" \n            -showSetMembers 1\n            -allowMultiSelection 1\n            -alwaysToggleSelect 0\n            -directSelect 0\n            -displayMode \"DAG\" \n            -expandObjects 0\n            -setsIgnoreFilters 1\n            -containersIgnoreFilters 0\n            -editAttrName 0\n            -showAttrValues 0\n            -highlightSecondary 0\n            -showUVAttrsOnly 0\n            -showTextureNodesOnly 0\n            -attrAlphaOrder \"default\" \n            -animLayerFilterOptions \"allAffecting\" \n            -sortOrder \"none\" \n            -longNames 0\n            -niceNames 1\n            -showNamespace 1\n            -showPinIcons 0\n"
		+ "            -mapMotionTrails 0\n            -ignoreHiddenAttribute 0\n            -ignoreOutlinerColor 0\n            -renderFilterVisible 0\n            $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"graphEditor\" (localizedPanelLabel(\"Graph Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Graph Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"OutlineEd\");\n            outlinerEditor -e \n                -showShapes 1\n                -showAssignedMaterials 0\n                -showTimeEditor 1\n                -showReferenceNodes 0\n                -showReferenceMembers 0\n                -showAttributes 1\n                -showConnected 1\n                -showAnimCurvesOnly 1\n                -showMuteInfo 0\n                -organizeByLayer 1\n                -organizeByClip 1\n                -showAnimLayerWeight 1\n                -autoExpandLayers 1\n"
		+ "                -autoExpand 1\n                -showDagOnly 0\n                -showAssets 1\n                -showContainedOnly 0\n                -showPublishedAsConnected 0\n                -showParentContainers 1\n                -showContainerContents 0\n                -ignoreDagHierarchy 0\n                -expandConnections 1\n                -showUpstreamCurves 1\n                -showUnitlessCurves 1\n                -showCompounds 0\n                -showLeafs 1\n                -showNumericAttrsOnly 1\n                -highlightActive 0\n                -autoSelectNewObjects 1\n                -doNotSelectNewObjects 0\n                -dropIsParent 1\n                -transmitFilters 1\n                -setFilter \"0\" \n                -showSetMembers 0\n                -allowMultiSelection 1\n                -alwaysToggleSelect 0\n                -directSelect 0\n                -displayMode \"DAG\" \n                -expandObjects 0\n                -setsIgnoreFilters 1\n                -containersIgnoreFilters 0\n                -editAttrName 0\n"
		+ "                -showAttrValues 0\n                -highlightSecondary 0\n                -showUVAttrsOnly 0\n                -showTextureNodesOnly 0\n                -attrAlphaOrder \"default\" \n                -animLayerFilterOptions \"allAffecting\" \n                -sortOrder \"none\" \n                -longNames 0\n                -niceNames 1\n                -showNamespace 1\n                -showPinIcons 1\n                -mapMotionTrails 1\n                -ignoreHiddenAttribute 0\n                -ignoreOutlinerColor 0\n                -renderFilterVisible 0\n                $editorName;\n\n\t\t\t$editorName = ($panelName+\"GraphEd\");\n            animCurveEditor -e \n                -displayKeys 1\n                -displayTangents 0\n                -displayActiveKeys 0\n                -displayActiveKeyTangents 1\n                -displayInfinities 0\n                -displayValues 0\n                -autoFit 1\n                -autoFitTime 0\n                -snapTime \"integer\" \n                -snapValue \"none\" \n                -showResults \"off\" \n"
		+ "                -showBufferCurves \"off\" \n                -smoothness \"fine\" \n                -resultSamples 1\n                -resultScreenSamples 0\n                -resultUpdate \"delayed\" \n                -showUpstreamCurves 1\n                -showCurveNames 0\n                -showActiveCurveNames 0\n                -stackedCurves 0\n                -stackedCurvesMin -1\n                -stackedCurvesMax 1\n                -stackedCurvesSpace 0.2\n                -displayNormalized 0\n                -preSelectionHighlight 0\n                -constrainDrag 0\n                -classicMode 1\n                -valueLinesToggle 1\n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dopeSheetPanel\" (localizedPanelLabel(\"Dope Sheet\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Dope Sheet\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"OutlineEd\");\n"
		+ "            outlinerEditor -e \n                -showShapes 1\n                -showAssignedMaterials 0\n                -showTimeEditor 1\n                -showReferenceNodes 0\n                -showReferenceMembers 0\n                -showAttributes 1\n                -showConnected 1\n                -showAnimCurvesOnly 1\n                -showMuteInfo 0\n                -organizeByLayer 1\n                -organizeByClip 1\n                -showAnimLayerWeight 1\n                -autoExpandLayers 1\n                -autoExpand 0\n                -showDagOnly 0\n                -showAssets 1\n                -showContainedOnly 0\n                -showPublishedAsConnected 0\n                -showParentContainers 1\n                -showContainerContents 0\n                -ignoreDagHierarchy 0\n                -expandConnections 1\n                -showUpstreamCurves 1\n                -showUnitlessCurves 0\n                -showCompounds 1\n                -showLeafs 1\n                -showNumericAttrsOnly 1\n                -highlightActive 0\n"
		+ "                -autoSelectNewObjects 0\n                -doNotSelectNewObjects 1\n                -dropIsParent 1\n                -transmitFilters 0\n                -setFilter \"0\" \n                -showSetMembers 0\n                -allowMultiSelection 1\n                -alwaysToggleSelect 0\n                -directSelect 0\n                -displayMode \"DAG\" \n                -expandObjects 0\n                -setsIgnoreFilters 1\n                -containersIgnoreFilters 0\n                -editAttrName 0\n                -showAttrValues 0\n                -highlightSecondary 0\n                -showUVAttrsOnly 0\n                -showTextureNodesOnly 0\n                -attrAlphaOrder \"default\" \n                -animLayerFilterOptions \"allAffecting\" \n                -sortOrder \"none\" \n                -longNames 0\n                -niceNames 1\n                -showNamespace 1\n                -showPinIcons 0\n                -mapMotionTrails 1\n                -ignoreHiddenAttribute 0\n                -ignoreOutlinerColor 0\n                -renderFilterVisible 0\n"
		+ "                $editorName;\n\n\t\t\t$editorName = ($panelName+\"DopeSheetEd\");\n            dopeSheetEditor -e \n                -displayKeys 1\n                -displayTangents 0\n                -displayActiveKeys 0\n                -displayActiveKeyTangents 0\n                -displayInfinities 0\n                -displayValues 0\n                -autoFit 0\n                -autoFitTime 0\n                -snapTime \"integer\" \n                -snapValue \"none\" \n                -outliner \"dopeSheetPanel1OutlineEd\" \n                -showSummary 1\n                -showScene 0\n                -hierarchyBelow 0\n                -showTicks 1\n                -selectionWindow 0 0 0 0 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"timeEditorPanel\" (localizedPanelLabel(\"Time Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Time Editor\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"clipEditorPanel\" (localizedPanelLabel(\"Trax Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Trax Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = clipEditorNameFromPanel($panelName);\n            clipEditor -e \n                -displayKeys 0\n                -displayTangents 0\n                -displayActiveKeys 0\n                -displayActiveKeyTangents 0\n                -displayInfinities 0\n                -displayValues 0\n                -autoFit 0\n                -autoFitTime 0\n                -snapTime \"none\" \n                -snapValue \"none\" \n                -initialized 0\n                -manageSequencer 0 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"sequenceEditorPanel\" (localizedPanelLabel(\"Camera Sequencer\")) `;\n"
		+ "\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Camera Sequencer\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = sequenceEditorNameFromPanel($panelName);\n            clipEditor -e \n                -displayKeys 0\n                -displayTangents 0\n                -displayActiveKeys 0\n                -displayActiveKeyTangents 0\n                -displayInfinities 0\n                -displayValues 0\n                -autoFit 0\n                -autoFitTime 0\n                -snapTime \"none\" \n                -snapValue \"none\" \n                -initialized 0\n                -manageSequencer 1 \n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"hyperGraphPanel\" (localizedPanelLabel(\"Hypergraph Hierarchy\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Hypergraph Hierarchy\")) -mbv $menusOkayInPanels  $panelName;\n"
		+ "\n\t\t\t$editorName = ($panelName+\"HyperGraphEd\");\n            hyperGraph -e \n                -graphLayoutStyle \"hierarchicalLayout\" \n                -orientation \"horiz\" \n                -mergeConnections 1\n                -zoom 0.739895\n                -animateTransition 0\n                -showRelationships 1\n                -showShapes 1\n                -showDeformers 0\n                -showExpressions 0\n                -showConstraints 0\n                -showConnectionFromSelected 0\n                -showConnectionToSelected 0\n                -showConstraintLabels 0\n                -showUnderworld 0\n                -showInvisible 1\n                -transitionFrames 5\n                -currentNode \"annotationLocator1\" \n                -opaqueContainers 0\n                -freeform 0\n                -imagePosition 0 0 \n                -imageScale 1\n                -imageEnabled 0\n                -graphType \"DAG\" \n                -heatMapDisplay 0\n                -updateSelection 1\n                -updateNodeAdded 1\n"
		+ "                -useDrawOverrideColor 0\n                -limitGraphTraversal -1\n                -range 0 0 \n                -iconSize \"largeIcons\" \n                -showCachedConnections 0\n                $editorName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"hyperShadePanel\" (localizedPanelLabel(\"Hypershade\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Hypershade\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"visorPanel\" (localizedPanelLabel(\"Visor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Visor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"nodeEditorPanel\" (localizedPanelLabel(\"Node Editor\")) `;\n"
		+ "\tif ($nodeEditorPanelVisible || $nodeEditorWorkspaceControlOpen) {\n\t\tif (\"\" == $panelName) {\n\t\t\tif ($useSceneConfig) {\n\t\t\t\t$panelName = `scriptedPanel -unParent  -type \"nodeEditorPanel\" -l (localizedPanelLabel(\"Node Editor\")) -mbv $menusOkayInPanels `;\n\n\t\t\t$editorName = ($panelName+\"NodeEditorEd\");\n            nodeEditor -e \n                -allAttributes 0\n                -allNodes 0\n                -autoSizeNodes 1\n                -consistentNameSize 1\n                -createNodeCommand \"nodeEdCreateNodeCommand\" \n                -connectNodeOnCreation 0\n                -connectOnDrop 0\n                -copyConnectionsOnPaste 0\n                -defaultPinnedState 0\n                -additiveGraphingMode 0\n                -settingsChangedCallback \"nodeEdSyncControls\" \n                -traversalDepthLimit -1\n                -keyPressCommand \"nodeEdKeyPressCommand\" \n                -nodeTitleMode \"name\" \n                -gridSnap 0\n                -gridVisibility 1\n                -crosshairOnEdgeDragging 0\n                -popupMenuScript \"nodeEdBuildPanelMenus\" \n"
		+ "                -showNamespace 1\n                -showShapes 1\n                -showSGShapes 0\n                -showTransforms 1\n                -useAssets 1\n                -syncedSelection 1\n                -extendToShapes 1\n                -editorMode \"default\" \n                $editorName;\n\t\t\t}\n\t\t} else {\n\t\t\t$label = `panel -q -label $panelName`;\n\t\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Node Editor\")) -mbv $menusOkayInPanels  $panelName;\n\n\t\t\t$editorName = ($panelName+\"NodeEditorEd\");\n            nodeEditor -e \n                -allAttributes 0\n                -allNodes 0\n                -autoSizeNodes 1\n                -consistentNameSize 1\n                -createNodeCommand \"nodeEdCreateNodeCommand\" \n                -connectNodeOnCreation 0\n                -connectOnDrop 0\n                -copyConnectionsOnPaste 0\n                -defaultPinnedState 0\n                -additiveGraphingMode 0\n                -settingsChangedCallback \"nodeEdSyncControls\" \n                -traversalDepthLimit -1\n                -keyPressCommand \"nodeEdKeyPressCommand\" \n"
		+ "                -nodeTitleMode \"name\" \n                -gridSnap 0\n                -gridVisibility 1\n                -crosshairOnEdgeDragging 0\n                -popupMenuScript \"nodeEdBuildPanelMenus\" \n                -showNamespace 1\n                -showShapes 1\n                -showSGShapes 0\n                -showTransforms 1\n                -useAssets 1\n                -syncedSelection 1\n                -extendToShapes 1\n                -editorMode \"default\" \n                $editorName;\n\t\t\tif (!$useSceneConfig) {\n\t\t\t\tpanel -e -l $label $panelName;\n\t\t\t}\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"createNodePanel\" (localizedPanelLabel(\"Create Node\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Create Node\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"polyTexturePlacementPanel\" (localizedPanelLabel(\"UV Editor\")) `;\n"
		+ "\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"UV Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"renderWindowPanel\" (localizedPanelLabel(\"Render View\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Render View\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"shapePanel\" (localizedPanelLabel(\"Shape Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tshapePanel -edit -l (localizedPanelLabel(\"Shape Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextPanel \"posePanel\" (localizedPanelLabel(\"Pose Editor\")) `;\n\tif (\"\" != $panelName) {\n"
		+ "\t\t$label = `panel -q -label $panelName`;\n\t\tposePanel -edit -l (localizedPanelLabel(\"Pose Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dynRelEdPanel\" (localizedPanelLabel(\"Dynamic Relationships\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Dynamic Relationships\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"relationshipPanel\" (localizedPanelLabel(\"Relationship Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Relationship Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"referenceEditorPanel\" (localizedPanelLabel(\"Reference Editor\")) `;\n"
		+ "\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Reference Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"componentEditorPanel\" (localizedPanelLabel(\"Component Editor\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Component Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"dynPaintScriptedPanelType\" (localizedPanelLabel(\"Paint Effects\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Paint Effects\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"scriptEditorPanel\" (localizedPanelLabel(\"Script Editor\")) `;\n"
		+ "\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Script Editor\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"profilerPanel\" (localizedPanelLabel(\"Profiler Tool\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Profiler Tool\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\t$panelName = `sceneUIReplacement -getNextScriptedPanel \"contentBrowserPanel\" (localizedPanelLabel(\"Content Browser\")) `;\n\tif (\"\" != $panelName) {\n\t\t$label = `panel -q -label $panelName`;\n\t\tscriptedPanel -edit -l (localizedPanelLabel(\"Content Browser\")) -mbv $menusOkayInPanels  $panelName;\n\t\tif (!$useSceneConfig) {\n\t\t\tpanel -e -l $label $panelName;\n\t\t}\n\t}\n\n\n\tif ($useSceneConfig) {\n        string $configName = `getPanel -cwl (localizedPanelLabel(\"Current Layout\"))`;\n"
		+ "        if (\"\" != $configName) {\n\t\t\tpanelConfiguration -edit -label (localizedPanelLabel(\"Current Layout\")) \n\t\t\t\t-userCreated false\n\t\t\t\t-defaultImage \"vacantCell.xP:/\"\n\t\t\t\t-image \"\"\n\t\t\t\t-sc false\n\t\t\t\t-configString \"global string $gMainPane; paneLayout -e -cn \\\"quad\\\" -ps 1 50 50 -ps 2 50 50 -ps 3 50 50 -ps 4 50 50 $gMainPane;\"\n\t\t\t\t-removeAllPanels\n\t\t\t\t-ap false\n\t\t\t\t\t(localizedPanelLabel(\"Top View\")) \n\t\t\t\t\t\"modelPanel\"\n"
		+ "\t\t\t\t\t\"$panelName = `modelPanel -unParent -l (localizedPanelLabel(\\\"Top View\\\")) -mbv $menusOkayInPanels `;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -cam `findStartUpCamera top` \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 0\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 32768\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -greasePencils 1\\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 686\\n    -height 605\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t\t\"modelPanel -edit -l (localizedPanelLabel(\\\"Top View\\\")) -mbv $menusOkayInPanels  $panelName;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -cam `findStartUpCamera top` \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 0\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 32768\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -greasePencils 1\\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 686\\n    -height 605\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t-ap false\n\t\t\t\t\t(localizedPanelLabel(\"Persp View\")) \n\t\t\t\t\t\"modelPanel\"\n"
		+ "\t\t\t\t\t\"$panelName = `modelPanel -unParent -l (localizedPanelLabel(\\\"Persp View\\\")) -mbv $menusOkayInPanels `;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -cam `findStartUpCamera persp` \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 0\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 32768\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -greasePencils 1\\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 685\\n    -height 605\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t\t\"modelPanel -edit -l (localizedPanelLabel(\\\"Persp View\\\")) -mbv $menusOkayInPanels  $panelName;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -cam `findStartUpCamera persp` \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 0\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 32768\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -greasePencils 1\\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 685\\n    -height 605\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t-ap false\n\t\t\t\t\t(localizedPanelLabel(\"Hypergraph Hierarchy\")) \n\t\t\t\t\t\"scriptedPanel\"\n\t\t\t\t\t\"$panelName = `scriptedPanel -unParent  -type \\\"hyperGraphPanel\\\" -l (localizedPanelLabel(\\\"Hypergraph Hierarchy\\\")) -mbv $menusOkayInPanels `;\\n\\n\\t\\t\\t$editorName = ($panelName+\\\"HyperGraphEd\\\");\\n            hyperGraph -e \\n                -graphLayoutStyle \\\"hierarchicalLayout\\\" \\n                -orientation \\\"horiz\\\" \\n                -mergeConnections 1\\n                -zoom 0.739895\\n                -animateTransition 0\\n                -showRelationships 1\\n                -showShapes 1\\n                -showDeformers 0\\n                -showExpressions 0\\n                -showConstraints 0\\n                -showConnectionFromSelected 0\\n                -showConnectionToSelected 0\\n                -showConstraintLabels 0\\n                -showUnderworld 0\\n                -showInvisible 1\\n                -transitionFrames 5\\n                -currentNode \\\"annotationLocator1\\\" \\n                -opaqueContainers 0\\n                -freeform 0\\n                -imagePosition 0 0 \\n                -imageScale 1\\n                -imageEnabled 0\\n                -graphType \\\"DAG\\\" \\n                -heatMapDisplay 0\\n                -updateSelection 1\\n                -updateNodeAdded 1\\n                -useDrawOverrideColor 0\\n                -limitGraphTraversal -1\\n                -range 0 0 \\n                -iconSize \\\"largeIcons\\\" \\n                -showCachedConnections 0\\n                $editorName\"\n"
		+ "\t\t\t\t\t\"scriptedPanel -edit -l (localizedPanelLabel(\\\"Hypergraph Hierarchy\\\")) -mbv $menusOkayInPanels  $panelName;\\n\\n\\t\\t\\t$editorName = ($panelName+\\\"HyperGraphEd\\\");\\n            hyperGraph -e \\n                -graphLayoutStyle \\\"hierarchicalLayout\\\" \\n                -orientation \\\"horiz\\\" \\n                -mergeConnections 1\\n                -zoom 0.739895\\n                -animateTransition 0\\n                -showRelationships 1\\n                -showShapes 1\\n                -showDeformers 0\\n                -showExpressions 0\\n                -showConstraints 0\\n                -showConnectionFromSelected 0\\n                -showConnectionToSelected 0\\n                -showConstraintLabels 0\\n                -showUnderworld 0\\n                -showInvisible 1\\n                -transitionFrames 5\\n                -currentNode \\\"annotationLocator1\\\" \\n                -opaqueContainers 0\\n                -freeform 0\\n                -imagePosition 0 0 \\n                -imageScale 1\\n                -imageEnabled 0\\n                -graphType \\\"DAG\\\" \\n                -heatMapDisplay 0\\n                -updateSelection 1\\n                -updateNodeAdded 1\\n                -useDrawOverrideColor 0\\n                -limitGraphTraversal -1\\n                -range 0 0 \\n                -iconSize \\\"largeIcons\\\" \\n                -showCachedConnections 0\\n                $editorName\"\n"
		+ "\t\t\t\t-ap false\n\t\t\t\t\t(localizedPanelLabel(\"Front View\")) \n\t\t\t\t\t\"modelPanel\"\n"
		+ "\t\t\t\t\t\"$panelName = `modelPanel -unParent -l (localizedPanelLabel(\\\"Front View\\\")) -mbv $menusOkayInPanels `;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -cam `findStartUpCamera front` \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 0\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 32768\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -greasePencils 1\\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 686\\n    -height 605\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t\t\"modelPanel -edit -l (localizedPanelLabel(\\\"Front View\\\")) -mbv $menusOkayInPanels  $panelName;\\n$editorName = $panelName;\\nmodelEditor -e \\n    -cam `findStartUpCamera front` \\n    -useInteractiveMode 0\\n    -displayLights \\\"default\\\" \\n    -displayAppearance \\\"smoothShaded\\\" \\n    -activeOnly 0\\n    -ignorePanZoom 0\\n    -wireframeOnShaded 0\\n    -headsUpDisplay 1\\n    -holdOuts 1\\n    -selectionHiliteDisplay 1\\n    -useDefaultMaterial 0\\n    -bufferMode \\\"double\\\" \\n    -twoSidedLighting 0\\n    -backfaceCulling 0\\n    -xray 0\\n    -jointXray 0\\n    -activeComponentsXray 0\\n    -displayTextures 0\\n    -smoothWireframe 0\\n    -lineWidth 1\\n    -textureAnisotropic 0\\n    -textureHilight 1\\n    -textureSampling 2\\n    -textureDisplay \\\"modulate\\\" \\n    -textureMaxSize 32768\\n    -fogging 0\\n    -fogSource \\\"fragment\\\" \\n    -fogMode \\\"linear\\\" \\n    -fogStart 0\\n    -fogEnd 100\\n    -fogDensity 0.1\\n    -fogColor 0.5 0.5 0.5 1 \\n    -depthOfFieldPreview 1\\n    -maxConstantTransparency 1\\n    -rendererName \\\"vp2Renderer\\\" \\n    -objectFilterShowInHUD 1\\n    -isFiltered 0\\n    -colorResolution 256 256 \\n    -bumpResolution 512 512 \\n    -textureCompression 0\\n    -transparencyAlgorithm \\\"frontAndBackCull\\\" \\n    -transpInShadows 0\\n    -cullingOverride \\\"none\\\" \\n    -lowQualityLighting 0\\n    -maximumNumHardwareLights 1\\n    -occlusionCulling 0\\n    -shadingModel 0\\n    -useBaseRenderer 0\\n    -useReducedRenderer 0\\n    -smallObjectCulling 0\\n    -smallObjectThreshold -1 \\n    -interactiveDisableShadows 0\\n    -interactiveBackFaceCull 0\\n    -sortTransparent 1\\n    -controllers 1\\n    -nurbsCurves 1\\n    -nurbsSurfaces 1\\n    -polymeshes 1\\n    -subdivSurfaces 1\\n    -planes 1\\n    -lights 1\\n    -cameras 1\\n    -controlVertices 1\\n    -hulls 1\\n    -grid 1\\n    -imagePlane 1\\n    -joints 1\\n    -ikHandles 1\\n    -deformers 1\\n    -dynamics 1\\n    -particleInstancers 1\\n    -fluids 1\\n    -hairSystems 1\\n    -follicles 1\\n    -nCloths 1\\n    -nParticles 1\\n    -nRigids 1\\n    -dynamicConstraints 1\\n    -locators 1\\n    -manipulators 1\\n    -pluginShapes 1\\n    -dimensions 1\\n    -handles 1\\n    -pivots 1\\n    -textures 1\\n    -strokes 1\\n    -motionTrails 1\\n    -clipGhosts 1\\n    -greasePencils 1\\n    -shadows 0\\n    -captureSequenceNumber -1\\n    -width 686\\n    -height 605\\n    -sceneRenderFilter 0\\n    $editorName;\\nmodelEditor -e -viewSelected 0 $editorName;\\nmodelEditor -e \\n    -pluginObjects \\\"gpuCacheDisplayFilter\\\" 1 \\n    $editorName\"\n"
		+ "\t\t\t\t$configName;\n\n            setNamedPanelLayout (localizedPanelLabel(\"Current Layout\"));\n        }\n\n        panelHistory -e -clear mainPanelHistory;\n        sceneUIReplacement -clear;\n\t}\n\n\ngrid -spacing 5 -size 12 -divisions 5 -displayAxes yes -displayGridLines yes -displayDivisionLines yes -displayPerspectiveLabels no -displayOrthographicLabels no -displayAxesBold yes -perspectiveLabelPosition axis -orthographicLabelPosition edge;\nviewManip -drawCompass 0 -compassAngle 0 -frontParameters \"\" -homeParameters \"\" -selectionLockParameters \"\";\n}\n");
	setAttr ".scriptType" 3;
createNode script -name "sceneConfigurationScriptNode";
	rename -uuid "4E173CCB-4DAB-4501-1C31-C18614E88A0A";
	setAttr ".before" -type "string" "playbackOptions -min 1 -max 120 -ast 1 -aet 200 ";
	setAttr ".scriptType" 6;
select -noExpand :time1;
	setAttr ".outTime" 1;
	setAttr ".unwarpedTime" 1;
select -noExpand :hardwareRenderingGlobals;
	setAttr ".objectTypeFilterNameArray" -type "stringArray" 22 "NURBS Curves" "NURBS Surfaces" "Polygons" "Subdiv Surface" "Particles" "Particle Instance" "Fluids" "Strokes" "Image Planes" "UI" "Lights" "Cameras" "Locators" "Joints" "IK Handles" "Deformers" "Motion Trails" "Components" "Hair Systems" "Follicles" "Misc. UI" "Ornaments"  ;
	setAttr ".objectTypeFilterValueArray" -type "Int32Array" 22 0 1 1
		 1 1 1 1 1 1 0 0 0 0 0 0
		 0 0 0 0 0 0 0 ;
	setAttr ".floatingPointRTEnable" yes;
select -noExpand :renderPartition;
	setAttr -size 2 ".sets";
select -noExpand :renderGlobalsList1;
select -noExpand :defaultShaderList1;
	setAttr -size 4 ".shaders";
select -noExpand :postProcessList1;
	setAttr -size 2 ".postProcesses";
select -noExpand :defaultRenderingList1;
select -noExpand :initialShadingGroup;
	setAttr ".renderableOnlySet" yes;
select -noExpand :initialParticleSE;
	setAttr ".renderableOnlySet" yes;
select -noExpand :defaultRenderGlobals;
	setAttr ".startFrame" 1;
	setAttr ".endFrame" 10;
select -noExpand :defaultResolution;
	setAttr ".pixelAspect" 1;
select -noExpand :hardwareRenderGlobals;
	setAttr ".colorTextureResolution" 256;
	setAttr ".bumpTextureResolution" 512;
select -noExpand :ikSystem;
	setAttr -size 4 ".ikSolver";
connectAttr "pCube1_blend.output" "pCube1.blend";
connectAttr "gripNode5.outScale" "pCube1.scale";
connectAttr "gripNode5.outRotation" "pCube1.rotate";
connectAttr "gripNode5.outTranslation" "pCube1.translate";
connectAttr "polyCube1.output" "pCubeShape1.inMesh";
connectAttr "annotationLocator1Shape.worldMatrix" "annotationShape1.dagObjectMatrix"
		 -nextAvailable;
connectAttr "annotationLocator2Shape.worldMatrix" "annotationShape2.dagObjectMatrix"
		 -nextAvailable;
connectAttr "ik_translateX.output" "ik.translateX";
connectAttr "ik_translateY.output" "ik.translateY";
connectAttr "ik_translateZ.output" "ik.translateZ";
connectAttr "ik_rotateX.output" "ik.rotateX";
connectAttr "ik_rotateY.output" "ik.rotateY";
connectAttr "ik_rotateZ.output" "ik.rotateZ";
connectAttr "annotationLocator3Shape.worldMatrix" "annotationShape3.dagObjectMatrix"
		 -nextAvailable;
relationship "link" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "link" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialShadingGroup.message" ":defaultLightSet.message";
relationship "shadowLink" ":lightLinker1" ":initialParticleSE.message" ":defaultLightSet.message";
connectAttr "layerManager.displayLayerId[0]" "defaultLayer.identification";
connectAttr "renderLayerManager.renderLayerId[0]" "defaultRenderLayer.identification"
		;
connectAttr "gripNode5_inMatrix0.output" "gripNode5.inMatrix0";
connectAttr "gripNode5_inMatrix1.output" "gripNode5.inMatrix1";
connectAttr "pCube1.rotateOrder" "gripNode5.rotateOrder";
connectAttr "pCube1.grip0" "gripNode5.grip0";
connectAttr "pCube1.grip1" "gripNode5.grip1";
connectAttr "pCube1.blend" "gripNode5.weight";
connectAttr "pCube1.parentInverseMatrix" "gripNode5.parentInverseMatrix";
connectAttr "pCube1.grip0" "gripNode5_inMatrix0.selector";
connectAttr "|world.worldMatrix" "gripNode5_inMatrix0.input[0]";
connectAttr "ik.worldMatrix" "gripNode5_inMatrix0.input[1]";
connectAttr "ik.worldMatrix" "gripNode5_inMatrix0.input[2]";
connectAttr "pCube1.grip1" "gripNode5_inMatrix1.selector";
connectAttr "|world.worldMatrix" "gripNode5_inMatrix1.input[0]";
connectAttr "ik.worldMatrix" "gripNode5_inMatrix1.input[1]";
connectAttr "ik.worldMatrix" "gripNode5_inMatrix1.input[2]";
connectAttr "defaultRenderLayer.message" ":defaultRenderingList1.rendering" -nextAvailable
		;
connectAttr "pCubeShape1.instObjGroups" ":initialShadingGroup.dagSetMembers" -nextAvailable
		;
// End of grip_example.ma
