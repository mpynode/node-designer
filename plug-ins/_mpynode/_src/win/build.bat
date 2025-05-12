set MAYA_VERSION=%1

if /I "%MAYA_VERSION%" == "2023" (
    set MAYA_PYTHON_PATH="C:\Program Files\Autodesk\Maya2023\bin\mayapy.exe"
) else if /I "%MAYA_VERSION%" == "2024" (
    set MAYA_PYTHON_PATH="C:\Program Files\Autodesk\Maya2024\bin\mayapy.exe"
) else if /I "%MAYA_VERSION%" == "2025" (
    set MAYA_PYTHON_PATH="C:\Program Files\Autodesk\Maya2025\bin\mayapy.exe"
) else (
    echo "Please provide a valid version of Maya to build for"
    exit /b
)

%MAYA_PYTHON_PATH% ..\setup.py build_ext --inplace