// Print incoming references to a list of ROM addresses.
// Run via: analyzeHeadless <project> <name> -process <file> -scriptPath <this dir> -postScript FindXrefs.java <addr1> <addr2> ...
// Addresses are hex strings WITHOUT the 0x08000000 GBA base offset already added, e.g. 083FD7A2
// @category CharacterMode
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Reference;

public class FindXrefs extends GhidraScript {
    @Override
    protected void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length == 0) {
            println("USAGE: FindXrefs.java <hexaddr1> <hexaddr2> ...  (e.g. 083FD7A2)");
            return;
        }
        for (String hexaddr : args) {
            Address addr = toAddr(hexaddr);
            println("=== XREFs to 0x" + hexaddr + " ===");
            Reference[] refs = getReferencesTo(addr);
            int count = 0;
            for (Reference ref : refs) {
                count++;
                Address fromAddr = ref.getFromAddress();
                Function func = getFunctionContaining(fromAddr);
                String funcName = (func != null) ? func.getName() : "(no function)";
                String funcEntry = (func != null) ? func.getEntryPoint().toString() : "?";
                println("  from 0x" + fromAddr + "  in function " + funcName
                        + " @ " + funcEntry + "  type=" + ref.getReferenceType());
            }
            if (count == 0) {
                println("  (no references found)");
            }
            println("");
        }
    }
}
