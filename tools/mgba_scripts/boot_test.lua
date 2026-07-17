local H=dofile("tools/mgba_scripts/harness.lua")
H.onFrame(function(f)
  if f==200 then emu:screenshot("tools/savestates/boot.png"); H.log("booted ok f=200"); H.finish() end
end)
