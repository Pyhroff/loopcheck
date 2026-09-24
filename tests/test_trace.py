from loopcheck.trace import Step, Trace


def test_step_call_signature_ignores_arg_order():
    a = Step(index=0, tool_name="search", tool_args={"q": "x", "n": 5})
    b = Step(index=1, tool_name="search", tool_args={"n": 5, "q": "x"})
    assert a.call_signature() == b.call_signature()


def test_final_answer_step_has_no_signature():
    step = Step(index=0, tool_name=None, tool_result="the answer")
    assert step.call_signature() is None


def test_trace_round_trips_through_dict():
    t = Trace(agent_name="a", goal="g", steps=[Step(index=0, tool_name="x", tool_args={"a": 1})])
    back = Trace.from_dict(t.to_dict())
    assert back.agent_name == "a"
    assert back.steps[0].tool_name == "x"
    assert back.steps[0].tool_args == {"a": 1}


def test_total_cost_sums_all_steps():
    t = Trace(
        agent_name="a", goal="g", input_cost_per_1k=1.0, output_cost_per_1k=2.0,
        steps=[
            Step(index=0, input_tokens=1000, output_tokens=500),
            Step(index=1, input_tokens=2000, output_tokens=0),
        ],
    )
    # step0: 1*1.0 + 0.5*2.0 = 2.0 ; step1: 2*1.0 + 0 = 2.0 -> total 4.0
    assert t.total_cost() == 4.0
