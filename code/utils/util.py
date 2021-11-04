

def allocate_set(gpu_num):
    return profile_allocate_set(gpu_num)
    if gpu_num == 1:
        return [ [1] ]
    if gpu_num == 2:
        # return [ [2], [1, 1]]
        return [[2]]
    if gpu_num == 3:
        # return [ [3], [2, 1], [1, 1, 1]]
        return [[3]]
    if gpu_num == 4:
        return [[4]]
        # return [ [4],  [2, 2], [2, 1, 1], [1, 1, 1, 1]]
    if gpu_num == 5:
        # return [ [5], [4, 1], [3, 2], [3, 1, 1], [2, 2, 1]]
        return [[5]]
    if gpu_num == 6:
        # return [ [6], [4, 2], [3, 3], [4, 1, 1], [2, 2, 2]]
        return [[6]]
    if gpu_num == 7:
        # return [ [7], [6, 1], [5, 2], [4, 3], [5, 1, 1], [4, 2, 1], [3, 3, 1], [3, 2, 2]]
        return [[7]]
    if gpu_num == 8:
        # return [ [8], [6, 2], [4, 4], [6, 1, 1], [4, 2, 2]]
        return [[8]]
    return list()


def profile_allocate_set(gpu_num):
    if gpu_num == 1:
        return [ [1] ]
    if gpu_num == 2:
        return [ [2], [1, 1]]
    if gpu_num == 3:
        return [ [3], [2, 1]]
    if gpu_num == 4:
        return [ [4],  [2, 2]]
    if gpu_num == 5:
        return [ [5], [3, 2], [2, 2, 1]]
    if gpu_num == 6:
        return [ [6], [4, 2], [2, 2, 2]]
    if gpu_num == 7:
        return [ [7], [6, 1], [4, 3], [3, 2, 2]]
    if gpu_num == 8:
        return [ [8],[4, 4], [6, 2], [4, 2, 2], [2, 2, 2, 2]]
    return list()


def search_dict_list(dict_list, key, value):
    '''
    Search the targeted <key, value> in the dict_list
    Return:
        list entry, or just None 
    '''
    for e in dict_list:
        # if e.has_key(key) == True:
        if key in e:
            if e[key] == value:
                return e

    return None