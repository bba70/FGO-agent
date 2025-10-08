import sys
print(sys.path)

from repositories import MemoryDAL

if __name__ == '__main__':
    dal = MemoryDAL()
    
    # session = dal.get_session_by_id('72a83a41-5259-486d-aa78-b3c382b19675_20251008070623334091' )
    # print(session) 

    # sessions = dal.get_user_sessions('cca9126f-9b9a-457a-84fb-ebc43749769b_20251008070133119670')
    # print(sessions)

    # i = dal.update_session_name('72a83a41-5259-486d-aa78-b3c382b19675_20251008070623334091', '会话2')
    # print(i)

    # i = dal.deactivate_session('72a83a41-5259-486d-aa78-b3c382b19675_20251008070623334091')
    # print(i)

    # i = dal.activate_session('72a83a41-5259-486d-aa78-b3c382b19675_20251008070623334091')
    # print(i)

    # count = dal.get_session_count_by_user('cca9126f-9b9a-457a-84fb-ebc43749769b_20251008070133119670')
    # print(count)

    # count = dal.get_message_count('72a83a41-5259-486d-aa78-b3c382b19675_20251008070623334091')
    # print(count)

    i = dal.delete_session('72a83a41-5259-486d-aa78-b3c382b19675_20251008070623334091')
    print(i)