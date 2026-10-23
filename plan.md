1. **Refactor `_build` in `backend/app/api/v1/endpoints/portal.py`**
   - The `_build` function is quite long and does multiple things (fetching EAP items, fetching documents, fetching protocols, fetching open tasks, etc.).
   - I will extract the individual querying pieces into small helper functions:
     - `_get_physical_progress_and_milestones(db, project, user)` -> `(float, List[PortalMilestone])`
     - `_get_current_documents(db, project, user)` -> `List[PortalDocument]`
     - `_get_protocols(db, project, user)` -> `List[PortalProtocol]`
     - `_get_open_tasks_count(db, project, user)` -> `int`
   - This keeps the behavior intact but drastically reduces the length and complexity of `_build`.

2. **Verify changes**
   - Run the portal tests to ensure everything passes and the line coverage remains at 100%.

3. **Complete pre-commit steps**
   - Complete pre-commit steps to ensure proper testing, verification, review, and reflection are done.

4. **Submit PR**
   - Push code to a branch and submit with the code health description.
