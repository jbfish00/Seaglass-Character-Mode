// Run Ghidra's Decompiler on specific functions and print the C-like output.
// Run via: analyzeHeadless <project> <name> -process <file> -noanalysis
//   -scriptPath <this dir> -postScript DecompileFunc.java <addr1> <addr2> ...
// Addresses are hex WITHOUT the 0x08000000 base, e.g. 000CF068
// @category CharacterMode
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.util.task.ConsoleTaskMonitor;

public class DecompileFunc extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length == 0) {
            println("USAGE: DecompileFunc.java <hexaddr1> <hexaddr2> ...");
            return;
        }

        DecompInterface ifc = new DecompInterface();
        ifc.openProgram(currentProgram);

        for (String hexaddr : args) {
            Address addr = toAddr(hexaddr);
            Function func = getFunctionContaining(addr);
            if (func == null) {
                println("=== 0x" + hexaddr + ": no function found ===");
                continue;
            }
            println("=== " + func.getName() + " @ " + func.getEntryPoint() + " ===");
            DecompileResults res = ifc.decompileFunction(func, 60, new ConsoleTaskMonitor());
            if (res.decompileCompleted()) {
                println(res.getDecompiledFunction().getC());
            } else {
                println("  decompile failed: " + res.getErrorMessage());
            }
            println("");
        }
        ifc.dispose();
    }
}
