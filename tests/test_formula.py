"""
Test Formulas.
"""

import redzed

async def test_decorartor(circuit):
    """Test @formula"""

    redzed.Memory("v1", comment="value #1", initial=False)
    redzed.Memory("v2", comment="value #2", initial=False)

    @redzed.formula
    def v1_and_v2(v1, v2):
        """
        comment here
        text
        """
        return v1 and v2

    @redzed.formula
    def frml(v1, v2):
        return v1 or v2

    formulas = list(circuit.get_items(redzed.Formula))
    assert len(formulas) == 2
    f1 = circuit.resolve_name('v1_and_v2')
    f2 = circuit.resolve_name('frml')
    assert f1 in formulas
    assert f1.name == 'v1_and_v2'
    assert f1.comment == 'comment here'
    assert f2 in formulas
    assert f2.name == 'frml'
    assert f2.comment == ''
