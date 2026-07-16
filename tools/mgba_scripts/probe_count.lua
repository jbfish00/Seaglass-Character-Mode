local H=dofile("tools/mgba_scripts/harness.lua")
H.onFrame(function(f) if f~=60 then return end
  for _,a in ipairs({0x02019C1D,0x02019C1C,0x02019C1E,0x02019C1F}) do
    H.log(string.format("count@0x%08X = %d", a, emu:read8(a)))
  end
  H.finish() end)