''' -- imports from python libraries -- '''
import json
import bson
from bson.json_util import dumps
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_control
''' -- imports from installed packages -- '''
try:
    from bson import ObjectId
except ImportError:
    from pymongo.objectid import ObjectId

from bson import json_util

from django.http import HttpResponseRedirect, HttpResponse, StreamingHttpResponse
from django.contrib.auth.admin import User
from django.views.decorators.csrf import csrf_exempt

''' -- imports from application folders/files -- '''
from gnowsys_ndf.ndf.models import GSystemType, GSystem , Group  #, Node, GSystem  #, Triple
from gnowsys_ndf.ndf.models import db_utils, query_utils
from gnowsys_ndf.ndf.models import NodeJSONEncoder
from gnowsys_ndf.ndf.models import node_collection,triple_collection
from gnowsys_ndf.ndf.views.methods import get_group_name_id
from gnowsys_ndf.ndf.views.filehive import write_files


with open('gnowsys_ndf/gstudio_configs/api.json') as api_configs_json:
    api_configs = json.load(api_configs_json)

with open('gnowsys_ndf/gstudio_configs/verbose.json') as field_verbose_json:
    field_verbose_configs = json.load(field_verbose_json)


gst_api_fields_dict = {k: 1 for k in api_configs['fields']}

api_name_model_name_dict = {v: k for v, k in field_verbose_configs.iteritems()}


# TODO: write decorator for making JSON result OPEN API or JSON api compliance
@csrf_exempt
@cache_control(must_revalidate=True, max_age=6)
def db_schema(request, collection_name='', field_name='', field_value=''):
    '''
    GET /api/v2/schema
    {"Filehives": ["Filehive"], "Triples": ["GAttribute", "GRelation"], "Buddies": ["Buddy"], "Benchmarks": ["Benchmark"], "Nodes": ["MetaType", "GSystemType", "RelationType", "AttributeType", "GSystem", "Group", "ToReduceDocs", "Author"], "Counters": ["Counter"]}

    GET /api/v2/schema/Filehive
    ["_type", "first_uploader", "if_image_dimensions", "relurl", "first_parent", "uploaded_at", "filename", "length", "if_image_size_name", "md5", "mime_type"]

    # following URL will list all possible md5:
    GET /api/v2/schema/Filehive/md5/

    # following url will return matching document:
    GET /api/v2/schema/Filehive/md5/2bb048c86ae0aa3d0c496e00d128638bc3576f9dfe4f5aa15dc0a68088bea1c4
    '''
    # TODO: change logical sequence of `if` checking statements:
    if collection_name:
        # TODO: check for validity of collection_name.
        # get all class names and cache them. Use this list for validation.
        get_parameters_dict = query_dict = request.GET.dict()
        # print "get_parameters_dict: ", get_parameters_dict

        if field_value:
            query_dict.update({field_name: field_value})
            query_cur = query_utils.get_documents(collection_name, **query_dict)
            # print query_cur.count()
            # json_response = json.dumps(query_cur, cls=NodeJSONEncoder)
            json_response = json.dumps(list(query_cur), cls=NodeJSONEncoder)
            # print json_response

        elif field_name:
            # TODO: check for validity of field.
            # get all possible values from DB for provided field
            all_unique_field_values = query_utils.get_unique_values(collection_name, field_name)
            # print all_unique_field_values
            json_response = json.dumps(all_unique_field_values, cls=NodeJSONEncoder)
        else:
            json_response = json.dumps(db_utils.get_model_structure(collection_name).keys())

    else:  # if no collection_name then return DB schema
        json_response = json.dumps(db_utils.get_collection_hierarchy())

    return StreamingHttpResponse(json_response)


@csrf_exempt
@cache_control(must_revalidate=True, max_age=6)
def api_create_gs(request, gst_name="Page"):
    # curl -i -X POST -H "Content-Type: multipart/form-data" -F "filehive=@CIET-Mix.csv" -F "content=hey, this is sample content" -F "name=Test the FAB" -F "tags=check, 1, 2, aa" -F 'user_name=administrator'  -F 'workspace=warehouse' http://172.17.0.2:8000/api/v2/create/File

    # print gst_name
    # print "===================:: ", request.POST
    # print "===================:: ", request.POST.dict()
    # print "===================:: ", request.FILES

    write_files(request, group_id=request.POST.get('workspace'), unique_gs_per_file=False, kwargs=request.POST.dict())
    return HttpResponse(1)

@cache_control(must_revalidate=True, max_age=6)
def api_get_gs_nodes(request):

    get_parameters_dict = request.GET.dict()

    if not get_parameters_dict:
        aggregated_dict = gst_api_fields_dict.copy()
        aggregated_dict.update(api_name_model_name_dict)
        aggregated_dict.pop('_id')

        query_parameters_dict = {
                                    'Fields': aggregated_dict.keys(),
                                    'Attributes': node_collection.find({'_type': 'AttributeType'}).distinct('name'),
                                    'Relations': node_collection.find({'_type': 'RelationType'}).distinct('name')
                                }
        return HttpResponse(json.dumps(query_parameters_dict, indent=4), content_type='application/json')


    # GET: api/v1/<group_id>/<files>/<nroer_team>/
    exception_occured = ''
    oid_name_dict = {}
    gst_id = None
    # try:
    #     group_id = ObjectId(group_name_or_id)
    # except Exception as e:
    #     group_name, group_id = get_group_name_id(group_name_or_id)
    #     oid_name_dict[group_id] = group_name

    gsystem_structure_dict = GSystem.structure
    gsystem_keys = gsystem_structure_dict.keys()

    gst_all_fields_dict = {i: 1 for i in gsystem_keys}

    query_dict = {
                    '_type': 'GSystem',
                    'status': u'PUBLISHED',
                    'access_policy': 'PUBLIC',
                    # 'group_set': ObjectId(group_id),
                    # 'member_of': ObjectId(gst_id),
                    # 'created_by': user_id,
                }

    sample_gs = GSystem()
    attributes = {}

    # GET parameters:
    get_created_by = request.GET.get('created_by', None)
    if get_created_by:
        username_or_id_int = 0
        try:
            username_or_id_int = int(get_created_by)
        except Exception as e:
            pass

        auth_obj = node_collection.one({'_type': u'Author', '$or': [{'name': unicode(get_created_by)}, {'created_by': username_or_id_int} ] })
        if auth_obj:
            oid_name_dict[auth_obj._id] = auth_obj.name
            # user_id = auth_obj.created_by
            get_parameters_dict['created_by'] = auth_obj.created_by
        else:
            return HttpResponse('Requested user does not exists.', content_type='text/plain')

    get_resource_type = request.GET.get('resource_type', None)
    if get_resource_type:
        gst_name, gst_id = GSystemType.get_gst_name_id(get_resource_type)
        oid_name_dict[gst_id] = gst_name
        get_parameters_dict['member_of'] = [gst_id]
        attributes = sample_gs.get_possible_attributes([gst_id])

    get_workspace = request.GET.get('workspace', None)
    if get_workspace:
        group_name, group_id = Group.get_group_name_id(get_workspace)
        oid_name_dict[group_id] = group_name
        get_parameters_dict['group_set'] = [group_id]

    for key, val in get_parameters_dict.iteritems():
        stripped_key = key.split('.')[0]
        if stripped_key in gsystem_keys:
            query_dict.update({ key: ({'$regex': val, '$options': 'i'} if isinstance(gsystem_structure_dict[stripped_key], basestring or unicode) else val) })

        elif stripped_key in gst_attributes(gst_id):
            query_dict.update({('attribute_set.' + stripped_key): {'$regex': val, '$options': 'i'}})

    # print "query_dict: ", query_dict

    human = eval(request.GET.get('human', '1'))

    gst_fields = gst_api_fields_dict if human else gst_all_fields_dict

    all_resources = node_collection.find(query_dict, gst_fields)

    if human:
        gst_fields = gst_api_fields_dict

        # converting ids to human readable names:
        # Django User:
        user_fields = ['created_by', 'modified_by', 'contributors']
        all_users = []
        for each_field in user_fields:
            all_users += all_resources.distinct(each_field)
        all_users = list(set(all_users))

        userid_name_dict_cur = node_collection.find({'_type': u'Author', 'created_by': {'$in': all_users}}, {'name': 1, 'created_by': 1, '_id': 0})
        userid_name_dict = {i['created_by']: i['name'] for i in userid_name_dict_cur}

        # Mongo ids
        oid_fields = [ k for k, v in gsystem_structure_dict.iteritems() if v in [bson.objectid.ObjectId, [bson.objectid.ObjectId]] ]
        all_oid_list = []
        for each_field in oid_fields:
            all_oid_list += all_resources.distinct(each_field)
        all_oid_list = list(set(all_oid_list))

        oid_name_dict_cur = node_collection.find({'_id': {'$in': all_oid_list}}, {'name': 1})
        oid_name_dict = {i['_id']: i['name'] for i in oid_name_dict_cur}

        python_cur_list = []
        python_cur_list_append = python_cur_list.append
        for each_gs in all_resources:

            # attaching attributes:
            # NEEDS to optimize.
            for key, value in each_gs.get_possible_attributes(each_gs.member_of).iteritems():
                each_gs[key] = value['data_type']
                each_gs[key] = value['object_value']

            # mapping user id to username.
            for each_field in user_fields:
                each_gs[each_field] = [userid_name_dict.get(i, i) for i in each_gs[each_field]] if isinstance(each_gs[each_field], list) else userid_name_dict.get(each_gs[each_field], each_gs[each_field])

            # mapping mongo _id to name.
            for each_field in oid_fields:
                each_gs[each_field] = [oid_name_dict.get(i, i) for i in each_gs[each_field]] if isinstance(each_gs[each_field], list) else oid_name_dict[each_gs[each_field]]

            python_cur_list_append(each_gs)

        json_result = json.dumps(python_cur_list, cls=NodeJSONEncoder, sort_keys=True, indent=4)

    else:
        json_result = dumps(all_resources, sort_keys=True, indent=4)

    return HttpResponse(json_result, content_type='application/json')


# helper methods:
def gst_attributes(gst_name_or_id):

    if not gst_name_or_id:
        return node_collection.find({'_type': 'AttributeType'}).distinct('name')

    try:
        gst_id = ObjectId(gst_name_or_id)
    except Exception as e:
        gst_name, gst_id = GSystemType.get_gst_name_id(gst_name_or_id)

    return [at.name for at in node_collection.find({'_type': 'AttributeType', 'subject_type': gst_id})]


@cache_control(must_revalidate=True, max_age=6)
def api_get_field_values(request, field_name):
    '''
    GET /api/v2/tags
    '''
    field_name = api_name_model_name_dict.get(field_name, field_name)
    gsystem_structure_dict = GSystem.structure
    gsystem_keys = gsystem_structure_dict.keys()

    if field_name in gsystem_keys:
        json_result = '[]'
        oid_fields = [ k for k, v in gsystem_structure_dict.iteritems() if v in [bson.objectid.ObjectId, [bson.objectid.ObjectId]] ]
        user_fields = ['created_by', 'modified_by', 'contributors']

        # MONGO
        if field_name in oid_fields:
            result_list = node_collection.find({ '_id': {'$in': node_collection.find({}).distinct(field_name) } }).distinct('name')
        # USER
        elif field_name in user_fields:
            # mapping user id to username.
            result_list = node_collection.find({'_type': 'Author', 'created_by': {'$in': node_collection.find({}).distinct(field_name) } }).distinct('name')
        # OTHER
        else:
            # overriden from settings
            GSTUDIO_WORKING_GAPPS = [u'Page', u'File']
            gstudio_working_gapps_mof_list = node_collection.find({'_type': 'GSystemType', 'name': {'$in': GSTUDIO_WORKING_GAPPS} }).distinct('_id')
            result_list = node_collection.find({'_type': 'GSystem', 'status': u'PUBLISHED', 'access_policy': 'PUBLIC', 'member_of': {'$in': gstudio_working_gapps_mof_list}}).distinct(field_name)

        return HttpResponse(json.dumps(result_list, ensure_ascii=False, cls=NodeJSONEncoder, sort_keys=True, indent=4).encode('utf16'), content_type='application/json')

    elif field_name in node_collection.find({'_type': 'AttributeType'}).distinct('name'):
        return HttpResponse( json.dumps(node_collection.find().distinct('attribute_set.' + field_name), sort_keys=True, indent=4), content_type='application/json')

    return HttpResponse(["Invalid Field"], content_type='application/json')
