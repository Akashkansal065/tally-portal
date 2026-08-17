# Tally Safety & Crash Prevention Rule

Before constructing or dispatching any HTTP XML or JSON payload to TallyPrime, all agents MUST strictly follow these rules:

1. **STRICT BAN ON SHELL-INTERPOLATED TDL FORMULAS**:
   - In shell/terminal environments (`bash`, `zsh`), `$$` is evaluated as the shell's PID (e.g. `92134`, `91765`) and `$VAR` evaluates to `""`.
   - **NEVER** write `<SYSTEM TYPE="Formulae">` with `$$IsPurchase:$VOUCHERTYPENAME` or `$$ExactMatch` in any script executed from shell.
   - Always fetch the raw collection (`<TYPE>Voucher</TYPE>`) and perform filtering in Python in-memory.

2. **ALWAYS SANITIZE INCOMING XML**:
   - Strip low-ASCII binary entities with `re.sub(r'&#\d+;', '', xml_str)` before XML ElementTree parsing.

3. **IN-PLACE MODIFICATIONS REQUIRE COMPOSITE KEYS**:
   - When altering or cancelling vouchers in automatic numbering series, always bind `REMOTEID`, `VCHKEY`, and `<GUID>` to prevent ghost sequence generation.

4. **USE CANCELLATION OVER HARD DELETE**:
   - Vouchers with active bill allocations or stock items should be cancelled with `<ISCANCELLED>Yes</ISCANCELLED>` (`"iscancelled": true`) to safely zero balances and reverse stock without integrity exceptions.

5. **VERIFY ACTIVE COMPANY**:
   - Ensure `<SVCURRENTCOMPANY>` matches the open company in Tally before batch jobs.
