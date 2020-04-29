from logging import getLogger

from galaxy import managers
from galaxy.managers.collections_util import (
    api_payload_to_create_params,
    dictify_dataset_collection_instance,
    dictify_element_reference
)
from galaxy.model import DatasetCollectionElement
from galaxy.web import expose_api
from galaxy.webapps.base.controller import (
    BaseAPIController,
    UsesLibraryMixinItems
)

log = getLogger(__name__)


class DatasetCollectionsController(
    BaseAPIController,
    UsesLibraryMixinItems,
):

    def __init__(self, app):
        super(DatasetCollectionsController, self).__init__(app)
        self.history_manager = managers.histories.HistoryManager(app)

    @expose_api
    def index(self, trans, **kwd):
        trans.response.status = 501
        return 'not implemented'

    @expose_api
    def create(self, trans, payload, **kwd):
        """
        * POST /api/dataset_collections:
            create a new dataset collection instance.

        :type   payload: dict
        :param  payload: (optional) dictionary structure containing:
            * collection_type: dataset colltion type to create.
            * instance_type:   Instance type - 'history' or 'library'.
            * name:            the new dataset collections's name
            * datasets:        object describing datasets for collection
        :rtype:     dict
        :returns:   element view of new dataset collection
        """
        # TODO: Error handling...
        create_params = api_payload_to_create_params(payload)
        instance_type = payload.pop("instance_type", "history")
        if instance_type == "history":
            history_id = payload.get('history_id')
            history_id = self.decode_id(history_id)
            history = self.history_manager.get_owned(history_id, trans.user, current_history=trans.history)
            create_params["parent"] = history
        elif instance_type == "library":
            folder_id = payload.get('folder_id')
            library_folder = self.get_library_folder(trans, folder_id, check_accessible=True)
            self.check_user_can_add_to_library_item(trans, library_folder, check_accessible=False)
            create_params["parent"] = library_folder
        else:
            trans.status = 501
            return
        dataset_collection_instance = self.__service(trans).create(trans=trans, **create_params)
        return dictify_dataset_collection_instance(dataset_collection_instance,
                                                   security=trans.security, parent=create_params["parent"])

    @expose_api
    def show(self, trans, instance_type, id, **kwds):
        dataset_collection_instance = self.__service(trans).get_dataset_collection_instance(
            trans,
            id=id,
            instance_type=instance_type,
        )
        if instance_type == 'history':
            parent = dataset_collection_instance.history
        elif instance_type == 'library':
            parent = dataset_collection_instance.folder
        else:
            trans.status = 501
            return
        return dictify_dataset_collection_instance(
            dataset_collection_instance,
            security=trans.security,
            parent=parent,
            view='element'
        )

    @expose_api
    def contents(self, trans, id, **kwds):
        """
        Show direct child contents of indicated dataset collection parent id
        GET /api/dataset_collection/{id}/contents

        Optional pagination parameters
            limit:  integer
            offset: integer
        """

        limit = kwds.get('limit', None)
        offset = kwds.get('offset', None)
        decoded_id = trans.app.security.decode_id(id)

        # lookup elements by parent id
        qry = trans.sa_session.query(DatasetCollectionElement)
        qry = qry.filter(DatasetCollectionElement.dataset_collection_id == decoded_id)
        qry = qry.order_by(DatasetCollectionElement.element_index)

        if limit is not None:
            qry = qry.limit(limit)
        if offset is not None:
            qry = qry.limit(offset)

        def process_element(dsc_element):
            result = dictify_element_reference(dsc_element, recursive=False, security=trans.security)
            trans.security.encode_all_ids(result, recursive=True)
            return result

        return [process_element(el) for el in qry]

    def __service(self, trans):
        service = trans.app.dataset_collections_service
        return service
