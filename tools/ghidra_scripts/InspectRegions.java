// Force-disassemble small windows around known literal-pool addresses (found
// via tools/find_pointer_refs.py's raw byte search) and identify/create the
// containing function, since full-ROM auto-analysis timed out before
// reaching these regions. Much faster than a full re-analysis: works on
// ~26 small windows instead of 32MB.
//
// GBA code is predominantly THUMB (16-bit), not ARM (32-bit) — the default
// disassemble() call decodes as ARM and produces garbage ("adcs r8,r0,#..."
// nonsense). This explicitly sets the TMode context register before
// disassembling, and clears any bad prior analysis at these addresses first.
//
// Run via: analyzeHeadless <project> <name> -process <file> -noanalysis
//   -scriptPath <this dir> -postScript InspectRegions.java <addr1> <addr2> ...
// Addresses are hex WITHOUT the 0x08000000 base, e.g. 000CEFEC
// @category CharacterMode
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.address.AddressSet;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import ghidra.program.model.listing.Function;
import ghidra.program.model.listing.Instruction;
import ghidra.program.model.listing.InstructionIterator;
import java.math.BigInteger;

public class InspectRegions extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length == 0) {
            println("USAGE: InspectRegions.java <hexaddr1> <hexaddr2> ...");
            return;
        }

        Register tmode = currentProgram.getProgramContext().getRegister("TMode");
        if (tmode == null) {
            println("ERROR: no TMode register found on this language - can't force Thumb mode");
            return;
        }

        for (String hexaddr : args) {
            Address literalAddr = toAddr(hexaddr);
            println("=== region around 0x" + hexaddr + " ===");

            Address winStart = literalAddr.subtract(0x60);
            Address winEnd = literalAddr.add(0x10);

            // clear any bad (ARM-mode) analysis from earlier attempts
            try {
                clearListing(winStart, winEnd);
            } catch (Exception e) {
                // fine if nothing to clear
            }

            // force Thumb mode across the window before disassembling
            currentProgram.getProgramContext().setRegisterValue(
                winStart, winEnd, new RegisterValue(tmode, BigInteger.ONE));

            try {
                disassemble(winStart);
            } catch (Exception e) {
                println("  disassemble() failed: " + e.getMessage());
            }

            Function func = getFunctionContaining(literalAddr.subtract(2));
            if (func == null) {
                try {
                    Function created = createFunction(winStart, null);
                    if (created != null) {
                        func = created;
                    }
                } catch (Exception e) {
                    // report below
                }
            }

            if (func != null) {
                println("  containing function: " + func.getName() + " @ " + func.getEntryPoint());
            } else {
                println("  no function identified yet");
            }

            println("  instructions in window:");
            InstructionIterator it = currentProgram.getListing().getInstructions(new AddressSet(winStart, winEnd), true);
            int count = 0;
            while (it.hasNext() && count < 60) {
                Instruction insn = it.next();
                println("    " + insn.getAddress() + ": " + insn);
                count++;
            }
            println("");
        }
    }
}
