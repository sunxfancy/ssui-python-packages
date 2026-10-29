from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
from runtime import build_env, context, run

ctx = context()
run([ctx['python'], '-c', """
import torch
from ssui_trellis_mps.metal import extension
from ssui_trellis_mps.topology import unique_rows, count_indices, compact_pairs
assert callable(extension().neighbors)
rows = torch.tensor([[0, 2], [0, 1], [0, 2]], dtype=torch.int32)
u, inverse, counts = unique_rows(rows)
assert torch.equal(u[inverse], rows)
assert counts.tolist() == [1, 2]
assert count_indices(inverse, 2).tolist() == [1, 2]
pairs = compact_pairs(torch.tensor([[0, -1, 2], [-1, 0, 1]], dtype=torch.int32))
assert [(a.tolist(), b.tolist()) for a,b in pairs] == [([0, 2], [0, 2]), ([0, 1], [1, 2])]
print('Native extension load and CPU topology checks passed; GPU runtime not validated')
"""], env=build_env(ctx))
