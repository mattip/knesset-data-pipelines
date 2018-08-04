from datapackage_pipelines.wrapper import ingest, spew
import logging, sh


parameters, datapackage, resources = ingest()


source = parameters['source']
target = parameters['target']


logging.info('uploading {} --> {}'.format(source, target))
cmd = sh.Command('python2')
rsync_args = ['/gsutil/gsutil', '-q', 'rsync', '-a', 'public-read', '-r', source, target]
ls_args = ['/gsutil/gsutil', 'ls', '-l', target]
for line in cmd(*rsync_args, _iter=True):
    logging.info(line)
for line in cmd(*ls_args, _iter=True):
    logging.info(line)


spew(dict(datapackage, resources=[]), [])
