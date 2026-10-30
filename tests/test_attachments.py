from types import SimpleNamespace
import pytest
from toolchain.attachments import validate_paths,upload
from toolchain.feedback import Submission
from toolchain.models import APIError,UserInputError


def test_caps_before_report(tmp_path):
    f=tmp_path/'sample.txt';f.write_text('synthetic')
    assert validate_paths([f])[0][1]=='text/plain'
    with pytest.raises(UserInputError):validate_paths([f]*4)


def test_server_cannot_choose_upload_destination(tmp_path):
    f=tmp_path/'sample.txt';f.write_text('synthetic')
    class Response:
        status_code=200
        def __init__(self,doc):self.doc=doc
        def json(self):return self.doc
    class Client:
        def get(self,*args,**kw):return Response({'attachments':True})
        def post(self,*args,**kw):return Response({'url':'https://evil.invalid/upload','headers':{}})
        def put(self,*args,**kw):raise AssertionError('no bytes may be sent')
    with pytest.raises(APIError):upload(SimpleNamespace(site_key='cyber',api_key='synthetic'),Submission({'report_id':'r-'+'a'*24},'b'*64),[f],client=Client())

@pytest.mark.parametrize('brand', ['cyber', 'ai'])
def test_real_flag_command_transports_only_selected_bytes(monkeypatch,tmp_path,brand):
    import json
    import httpx
    from click.testing import CliRunner
    from toolchain.main import cli
    from toolchain import feedback, attachments
    from toolchain.groups import flag
    from tests.test_feedback import BODY,CAP,RECEIPT
    selected=tmp_path/'private-evidence.txt';selected.write_bytes(b'synthetic evidence')
    requests=[];owner=[];key='ctk_SYNTHETIC_ATTACHMENT'
    def transport(req):
        requests.append(req)
        if req.method=='GET':return httpx.Response(200,json={**CAP,'brand':brand,'attachments':True})
        if req.method=='POST':
            data=json.loads(req.content)
            assert req.headers['x-api-key']==key
            if req.url.path.endswith('/attachments'):
                assert data['ownership_token']==owner[0]
                assert data['size']==18 and data['declared_type']=='text/plain'
                bucket='aitoolchain' if brand=='ai' else 'cybertoolchain'
                aid='a-'+'e'*32
                return httpx.Response(200,json={'attachment_id':aid,'url':f'https://{bucket}-feedback-quarantine.s3.amazonaws.com/q/{brand}/{RECEIPT["report_id"]}/{aid}?X-Amz-Expires=900&X-Amz-SignedHeaders=content-type%3Bcontent-length%3Bif-none-match','headers':{'Content-Type':'text/plain','Content-Length':'18','If-None-Match':'*'}})
            owner.append(data['ownership_token'])
            return httpx.Response(200,json={**RECEIPT,'brand':brand})
        assert req.method=='PUT'
        assert req.content==b'synthetic evidence'
        assert req.headers['content-length']=='18' and req.headers['if-none-match']=='*'
        assert 'x-api-key' not in req.headers and 'authorization' not in req.headers
        assert owner[0].encode() not in req.content
        return httpx.Response(200)
    client=httpx.Client(transport=httpx.MockTransport(transport))
    original=feedback.FeedbackClient
    monkeypatch.setattr(flag,'FeedbackClient',lambda config:original(config,client=client))
    realupload=attachments.upload
    monkeypatch.setattr(attachments,'upload',lambda config,submission,paths:realupload(config,submission,paths,client=client))
    result=CliRunner().invoke(cli,['--site',brand,'--api-key',key,'flag','--claim-id',BODY['claim_id'],'--claim-rev','3','--observed-hash',BODY['observed_hash'],'--kind','wrong','--predicate','mcp','--proposal',json.dumps(BODY['proposal']),'--tool','example','--attachment',str(selected)])
    assert result.exit_code==0,result.output
    assert json.loads(result.output)['persisted'] is True
    assert owner[0] not in result.output and key not in result.output and selected.name not in result.output
    assert [r.method for r in requests]==['GET','POST','GET','POST','PUT']
