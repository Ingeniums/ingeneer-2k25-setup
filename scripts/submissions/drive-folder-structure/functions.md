I need some helper functions i can use for managing folders and files in google drive:
- get folder id using path (the path starts from MyDrive)
- create_folder(parent_id, name) -> id
- grant_permission(id, emails, permission) -> failed[]
- get_child_ids(id) -> id[]

- ungrant_permission(id, emails, permission) -> failed[]
- move_file(id, new_parent_id) -> success?
- empty_folder(id)

also function for access granting/tokens if needed
