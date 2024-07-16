from album.api import Album

_album_instance = None

def get_album_instance():
    global _album_instance
    if _album_instance is None:
        _album_instance = Album.Builder().build()
        _album_instance.load_or_create_collection()
    return _album_instance

def get_catalogs():
    return get_album_instance().get_index_as_dict()['catalogs']

def get_groups(catalog):
    return set(solution['setup']['group'] for solution in next(cat for cat in get_catalogs() if cat['name'] == catalog)['solutions'])

def get_names(catalog, group):
    return set(solution['setup']['name'] for solution in next(cat for cat in get_catalogs() if cat['name'] == catalog)['solutions'] if solution['setup']['group'] == group)

def get_versions(catalog, group, name):
    return [solution['setup']['version'] for solution in next(cat for cat in get_catalogs() if cat['name'] == catalog)['solutions'] if solution['setup']['group'] == group and solution['setup']['name'] == name]

def get_solution_args(catalog, group, name, version):
    solution = next((sol for sol in next(cat for cat in get_catalogs() if cat['name'] == catalog)['solutions']
                     if sol['setup']['group'] == group and sol['setup']['name'] == name and sol['setup']['version'] == version), None)
    return solution['setup']['args'] if solution else []

def get_recently_executed_solutions():
    return get_album_instance().get_collection_index().get_recently_launched_solutions()

def get_recently_installed_solutions():
    return get_album_instance().get_collection_index().get_recently_installed_solutions()

def run_solution(catalog, group, name, version, args):
    return get_album_instance().run(f"{catalog}:{group}:{name}:{version}", args)

def install_solution(catalog, group, name, version):
    return get_album_instance().install(f"{catalog}:{group}:{name}:{version}")

def uninstall_solution(catalog, group, name, version):
    return get_album_instance().uninstall(f"{catalog}:{group}:{name}:{version}")

def test_solution(catalog, group, name, version):
    return get_album_instance().test(f"{catalog}:{group}:{name}:{version}")
