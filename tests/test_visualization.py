import pytest
import numpy as np
import matplotlib
matplotlib.use('Agg') # Use non-interactive backend for tests
from app.engines.fea.visualization import FEAVisualizer

def test_plot_mesh():
    nodes = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    elements = [[0, 1, 2, 3]]
    
    vis = FEAVisualizer()
    img_b64 = vis.plot_mesh(nodes, elements)
    assert img_b64 is not None
    assert img_b64[:4] == b"\x89PNG" # Standard PNG header in bytes

def test_plot_deformation():
    nodes = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    elements = [[0, 1, 2, 3]]
    u = np.array([[0.1, 0.1], [0.2, 0.2], [0.3, 0.3], [0.1, 0.1]])
    
    vis = FEAVisualizer()
    img_b64 = vis.plot_deformed_mesh(nodes, elements, u, displacement_scale=1.0)
    assert img_b64 is not None
    assert img_b64[:4] == b"\x89PNG"

def test_plot_stress_contour():
    nodes = np.array([[0, 0], [1, 0], [1, 1], [0, 1]])
    elements = [[0, 1, 2, 3]]
    stresses = np.array([90.0]) # 1 element
    
    vis = FEAVisualizer()
    img_b64 = vis.plot_von_mises(nodes, elements, von_mises=stresses)
    assert img_b64 is not None
    assert img_b64[:4] == b"\x89PNG"
