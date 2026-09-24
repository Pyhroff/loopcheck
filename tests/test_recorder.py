from loopcheck.recorder import TraceRecorder


def test_record_step_appends_in_order():
    rec = TraceRecorder(agent_name="a", goal="g", model="m")
    rec.record_step(tool_name="search", tool_args={"q": "x"})
    rec.record_step(tool_name=None, tool_result="done")

    assert [s.index for s in rec.trace.steps] == [0, 1]
    assert rec.trace.steps[0].tool_name == "search"
    assert rec.trace.steps[1].tool_name is None


def test_save_writes_valid_trace_json(tmp_path):
    rec = TraceRecorder(agent_name="a", goal="g", input_cost_per_1k=1.0, output_cost_per_1k=1.0)
    rec.record_step(tool_name="x", tool_args={}, input_tokens=100)
    out = tmp_path / "trace.json"
    rec.save(out)

    from loopcheck.trace import Trace
    loaded = Trace.load(out)
    assert loaded.agent_name == "a"
    assert loaded.steps[0].input_tokens == 100


def test_tool_args_defaults_to_empty_dict():
    rec = TraceRecorder(agent_name="a", goal="g")
    step = rec.record_step(tool_name="x")
    assert step.tool_args == {}


def test_record_step_without_turn_gets_its_own_turn():
    rec = TraceRecorder(agent_name="a", goal="g")
    s0 = rec.record_step(tool_name="x")
    s1 = rec.record_step(tool_name="y")
    assert s0.turn == 0
    assert s1.turn == 1


def test_record_parallel_steps_share_one_turn():
    rec = TraceRecorder(agent_name="a", goal="g")
    steps = rec.record_parallel_steps([
        {"tool_name": "a", "tool_args": {}},
        {"tool_name": "b", "tool_args": {}},
        {"tool_name": "c", "tool_args": {}},
    ])
    assert [s.turn for s in steps] == [0, 0, 0]
    assert [s.index for s in steps] == [0, 1, 2]


def test_turn_counter_continues_after_parallel_batch():
    rec = TraceRecorder(agent_name="a", goal="g")
    rec.record_parallel_steps([{"tool_name": "a"}, {"tool_name": "b"}])
    next_step = rec.record_step(tool_name="c")
    assert next_step.turn == 1


def test_record_parallel_steps_with_empty_list_returns_empty():
    rec = TraceRecorder(agent_name="a", goal="g")
    assert rec.record_parallel_steps([]) == []
