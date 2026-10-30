"""In-memory, one-shot file courier after a persisted CLI report receipt."""
from pathlib import Path
import hashlib
import json
import os
import re
from urllib.parse import urlsplit, parse_qs
import httpx
from .feedback import FEEDBACK_BASES
from .models import APIError, UserInputError, NetworkError

TYPES={'.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg','.webp':'image/webp','.gif':'image/gif','.pdf':'application/pdf','.txt':'text/plain','.md':'text/markdown'}


def validate_paths(paths):
    if len(paths)>3:raise UserInputError('Attach at most three files.')
    selected=[]
    for path in paths:
        path=Path(path)
        if path.is_symlink() or not path.is_file() or path.suffix.lower() not in TYPES:raise UserInputError('Attach a regular PNG, JPEG, WebP, GIF, PDF, text or Markdown file.')
        size=path.stat().st_size
        if not 0<size<=8*1024**2:raise UserInputError('Each attachment must be at most 8 MiB.')
        selected.append((path,TYPES[path.suffix.lower()],size))
    if sum(size for _,_,size in selected)>16*1024**2:raise UserInputError('Attachments must total at most 16 MiB.')
    return selected


def upload(config,submission,paths,*,client=None):
    selected=validate_paths(paths)
    if not selected:return
    if client is None:
        with httpx.Client(timeout=config.timeout,follow_redirects=False) as session:return upload(config,submission,paths,client=session)
    base=FEEDBACK_BASES[config.site_key]
    try:
        capability=client.get(base+'/feedback/capabilities',follow_redirects=False)
        if capability.status_code!=200 or capability.json().get('attachments') is not True:raise APIError('Your report was received; attachments are unavailable on this server.')
        for path,mime,size in selected:
            body=json.dumps({'brand':config.site_key,'report_id':submission.receipt['report_id'],
                'ownership_token':submission.ownership_token,'declared_type':mime,'size':size},separators=(',',':')).encode()
            response=client.post(base+'/agent/claim-reports/attachments',content=body,headers={
                'x-api-key':config.api_key,'content-type':'application/json','x-amz-content-sha256':hashlib.sha256(body).hexdigest()},follow_redirects=False)
            if response.status_code!=200:raise APIError('Your report was received; an attachment was refused.')
            signed=response.json();url=urlsplit(signed['url']);query=parse_qs(url.query);headers=signed['headers']
            bucket='aitoolchain' if config.site_key=='ai' else 'cybertoolchain'
            host=rf'{bucket}-feedback-quarantine\.s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com'
            if (url.scheme!='https' or url.username or url.password or url.port or url.fragment or not re.fullmatch(host,url.hostname or '')
                or not re.fullmatch('a-[a-f0-9]{32}',str(signed.get('attachment_id','')))
                or url.path!='/q/'+config.site_key+'/'+submission.receipt['report_id']+'/'+signed['attachment_id']
                or query.get('X-Amz-Expires')!=['900']
                or not {'content-type','content-length','if-none-match'}<=set(query.get('X-Amz-SignedHeaders',[''])[0].split(';'))
                or headers!={'Content-Type':mime,'Content-Length':str(size),'If-None-Match':'*'}):
                raise APIError('Your report was received; unsafe upload instructions were refused.')
            # Read only the file explicitly selected by this caller. No decoder,
            # original hash, cache, filename log or session credential crosses PUT.
            with os.fdopen(os.open(path,os.O_RDONLY|os.O_NOFOLLOW),'rb') as stream:
                if os.fstat(stream.fileno()).st_size!=size:raise UserInputError('The attachment changed before upload.')
                result=client.put(signed['url'],content=stream,headers=headers,follow_redirects=False)
            if not 200<=result.status_code<300:raise APIError('Your report was received; an attachment upload did not complete.')
    except (httpx.HTTPError,ValueError,KeyError,TypeError):
        raise NetworkError('Your report was received; attachment delivery is unconfirmed.') from None
