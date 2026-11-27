import numpy as np
import pytest

from fivewhys.rag.served import checked_vectors
from fivewhys.rag.vectorstore import VectorStore


def test_batch_preserves_ids_and_rank():
    vectors = VectorStore(2)
    vectors.add_batch([71, 52], [[1.,0.],[0.,1.]])
    vectors.add(12, [.8,.6])
    assert [i for i, _ in vectors.search([1.,0.])] == [71, 12, 52]


@pytest.mark.parametrize("rows", [[], [[float("nan"),1]], [[1]], [[0,0]], [[2,0]]])
def test_wrong_size_non_normalized_or_nonfinite_output(rows):
    with pytest.raises(ValueError):
        checked_vectors(rows, count=1, dim=2)
