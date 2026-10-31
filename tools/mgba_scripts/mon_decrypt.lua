-- Decrypt a party/box mon's 48-byte substructure block (Gen 3 layout, kept by
-- pokeemerald-expansion): key = personality ^ otId, order = personality % 24,
-- Growth substructure: species u16 @0, item u16 @2, experience u32 @4.
-- The checksum (u16 @ +0x1C, the sum of the decrypted u16s) validates it.
local M = {}
local ORDERS = { "GAEM","GAME","GEAM","GEMA","GMAE","GMEA","AGEM","AGME","AEGM","AEMG","AMGE","AMEG",
                 "EGAM","EGMA","EAGM","EAMG","EMGA","EMAG","MGAE","MGEA","MAGE","MAEG","MEGA","MEAG" }
function M.decode(addr)
    local pid, otid = emu:read32(addr), emu:read32(addr + 4)
    local key = pid ~ otid
    local words = {}
    for i = 0, 11 do words[i] = emu:read32(addr + 0x20 + 4 * i) ~ key end
    local sum = 0
    for i = 0, 11 do sum = (sum + (words[i] & 0xFFFF) + (words[i] >> 16)) & 0xFFFF end
    local pos = ORDERS[pid % 24 + 1]:find("G") - 1
    local g0, g1 = words[pos * 3], words[pos * 3 + 1]
    return { pid = pid, species = g0 & 0x7FF, exp = g1 & 0x1FFFFF, raw_exp = g1,
             ok = sum == emu:read16(addr + 0x1C), level = emu:read8(addr + 0x54) }
end
return M
