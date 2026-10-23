from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from arm_build import smoke

smoke(Path(__file__).parent)

from runtime import build_env, context, run
ctx = context()
run([ctx['python'], '-c', "import cv2, numpy as np, sys; net=cv2.dnn.readNetFromONNX(sys.argv[1]); net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV); net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU); x=np.array([-1,2,-3,4],dtype=np.float32).reshape(1,1,2,2); net.setInput(x); np.testing.assert_array_equal(net.forward(),np.maximum(x,0))", str(Path(__file__).with_name('dnn-smoke.onnx'))], env=build_env(ctx))
