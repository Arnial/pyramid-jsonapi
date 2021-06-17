import sqlalchemy

from itertools import (
    islice,
)
from pyramid.httpexceptions import (
    HTTPInternalServerError,
    HTTPBadRequest,
)
from sqlalchemy.orm.interfaces import (
    ONETOMANY,
    MANYTOMANY,
    MANYTOONE,
)

import pyramid_jsonapi.workflow as wf

stages = (
    'alter_query',
    'alter_result',
    'alter_related_query',
    'alter_related_result',
    'alter_results',
)


def get_results(view, stages):
    query = view.related_query(view.obj_id, view.rel)
    qinfo = view.rel_view.collection_query_info(view.request)
    rel_stages = getattr(view.rel_view, 'related_get').stages
    limit = qinfo['page[limit]']
    count = None

    if view.rel.direction is ONETOMANY or view.rel.direction is MANYTOMANY:
        many = True
        query = view.rel_view.query_add_sorting(query)
        query = view.rel_view.query_add_filtering(query)
        query = query.offset(qinfo['page[offset]'])
        query = query.limit(qinfo['page[limit]'])
        query = wf.execute_stage(view.rel_view, rel_stages, 'alter_query', query)
        objects_iterator = wf.loop.altered_objects_iterator(
            view.rel_view, rel_stages, 'alter_result', query
        )
        offset_count = 0
        if 'page[offset]' in view.request.params:
            offset_count = sum(1 for _ in islice(objects_iterator, qinfo['page[offset]']))
        res_objs = list(islice(objects_iterator, limit))
        if(qinfo['pj_include_count']):
            count = offset_count + len(res_objs) + sum(1 for _ in objects_iterator)
    else:
        many = False
        query = wf.execute_stage(view.rel_view, rel_stages, 'alter_query', query)
        res_objs = [wf.loop.get_one_altered_result_object(view.rel_view, rel_stages, query)]
        if(qinfo['pj_include_count']):
            count = 1

    results = wf.Results(
        view.rel_view,
        objects=res_objs,
        many=many,
        is_top=True,
        count=count,
        limit=limit
    )

    # Fill the relationships with related objects.
    # Stage 'alter_related_result' will run on each object.
    for res_obj in results.objects:
        wf.loop.fill_result_object_related(res_obj, rel_stages)

    return wf.execute_stage(view, stages, 'alter_results', results)


def workflow(view, stages):
    return get_results(view, stages).serialise()
