import uuid


class ActionUidFactory:
    def new_uid(self) -> str:
        return str(uuid.uuid4())
