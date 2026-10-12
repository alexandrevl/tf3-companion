from pathlib import Path

from lupa import LuaRuntime


def test_failed_request_write_retries_without_premature_acknowledgment():
    lua = LuaRuntime(unpack_returned_tuples=True)
    bridge_file = Path(__file__).parents[1] / "mod/tf3_companion_bridge/content/tf3_companion/bridge.script.lua"
    lua.execute(bridge_file.read_text(encoding="utf-8"))
    lua.execute("""
        local bridge = data()
        -- Isolate lifecycle behavior from game-only collection APIs.
        for i = 1, 40 do
            local name = debug.getupvalue(bridge.guiUpdate, i)
            if not name then break end
            if name == 'readClock' then
                debug.setupvalue(bridge.guiUpdate, i, function() return 100, 1200 end)
            elseif name == 'buildSnapshot' then
                debug.setupvalue(bridge.guiUpdate, i, function(reason, id)
                    return {meta={requestId=id}, errors={}}, 100
                end)
            end
        end
        local writes, delivered = 0, nil
        app = {
            getAllUserdata = function() return {'tf3c_request.lua'} end,
            loadUserdata = function() return {id=7} end,
            saveUserdata = function(_, _, snapshot)
                writes = writes + 1
                if writes == 1 then error('disk full') end
                delivered = snapshot.meta.requestId
            end
        }
        local state = {frame=59, lastGameTime=100}
        local gui = {
            get=function() return state end,
            set=function(_, value) state=value end
        }
        bridge.guiUpdate({}, nil, gui)
        assert(writes == 1 and state.lastRequestId == nil)
        assert(state.lastGameTime == 100)
        for i=1,59 do bridge.guiUpdate({}, nil, gui) end
        assert(writes == 1, 'failure must not retry on every GUI frame')
        bridge.guiUpdate({}, nil, gui)
        assert(writes == 2 and delivered == 7 and state.lastRequestId == 7)
        for i=1,60 do bridge.guiUpdate({}, nil, gui) end
        assert(writes == 2, 'successful request must not be answered twice')
    """)
