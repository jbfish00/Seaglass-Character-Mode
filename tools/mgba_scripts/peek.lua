local H = dofile("tools/mgba_scripts/harness.lua")
H.onFrame(function(f)
    if f==150 then emu:screenshot("tools/savestates/nc_end.png"); H.finish() end
end)
