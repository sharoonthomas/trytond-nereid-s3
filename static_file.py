# -*- coding: utf-8 -*-
"""
    static_file

    Static File

    :copyright: (c) 2013 by Openlabs Technologies & Consulting (P) Limited
    :license: BSD, see LICENSE for more details.
"""
from trytond.model import ModelSQL, ModelView, fields
from trytond.pyson import Eval, Bool
from boto.s3.connection import S3Connection
from boto.s3.key import Key
from trytond.pool import PoolMeta

__all__ = ['NereidStaticFolder', 'NereidStaticFile']
__metaclass__ = PoolMeta


class NereidStaticFolder(ModelSQL, ModelView):
    __name__ = "nereid.static.folder"
    _rec_name = "folder_name"

    s3_use_bucket = fields.Boolean("Use S3 Bucket?")
    s3_access_key = fields.Char(
        "S3 Access Key",
        states={'required': Bool(Eval('s3_use_bucket'))}
    )
    s3_secret_key = fields.Char(
        "S3 Secret Key",
        states={'required': Bool(Eval('s3_use_bucket'))}
    )
    s3_bucket_name = fields.Char(
        "S3 Bucket Name",
        states={'required': Bool(Eval('s3_use_bucket'))}
    )
    s3_cloudfront_cname = fields.Char(
        "S3 Cloudfront CNAME",
        states={'required': Bool(Eval('s3_use_bucket'))}
    )

    @classmethod
    def __setup__(cls):
        super(NereidStaticFolder, cls).__setup__()

        cls._constraints += [
            ('check_cloudfront_cname', 'invalid_cname'),
        ]
        cls._error_messages.update({
            "invalid_cname": "Cloudfront CNAME with '/' at the end is not " +
                "allowed",
        })

    def get_bucket(self):
        '''
        Return an S3 bucket for the static file
        '''
        s3_conn = S3Connection(
            self.s3_access_key, self.s3_secret_key
        )
        return s3_conn.get_bucket(self.s3_bucket_name)

    @staticmethod
    def default_s3_cloudfront_cname():
        """
        Sets default for Cloudfront CNAME
        """
        return "http://your-domain.cloudfront.net"

    def check_cloudfront_cname(self):
        """
        Checks for '/' at the end of Cloudfront CNAME
        """
        if self.s3_cloudfront_cname.endswith('/'):
            return False
        return True


class NereidStaticFile(ModelSQL, ModelView):
    __name__ = "nereid.static.file"

    folder = fields.Many2One(
        'nereid.static.folder', 'Folder', select=True, required=True,
        domain=[('s3_use_bucket', '=', Eval('is_s3_bucket'))],
        depends=['is_s3_bucket'],
    )
    type = fields.Selection([
        ('local', 'Local File'),
        ('remote', 'Remote File'),
        ('s3', 'S3'),
    ], 'File Type', on_change=['type', 's3_bucket'])

    is_s3_bucket = fields.Function(
        fields.Boolean("S3 Bucket?"), 'get_is_s3_bucket'
    )

    def get_url(self, name):
        """
        Return the URL for the given static file

        :param name: Field name
        """
        if self.type == 's3':
            return '/'.join(
                [self.folder.s3_cloudfront_cname, self.name]
            )
        return super(NereidStaticFile, self).get_url(name)

    def _set_file_binary(self, value):
        """
        Stores the file to amazon s3

        :param static_file: Browse record of the static file
        :param value: The value to set
        """
        if not value:
            return
        if self.type == "s3":
            bucket = self.folder.get_bucket()
            key = Key(bucket)
            key.key = self.name
            return key.set_contents_from_string(value)
        return super(NereidStaticFile, self)._set_file_binary(value)

    def get_file_binary(self, name):
        '''
        Getter for the binary_file field. This fetches the file from the
        Amazon s3

        :param name: Field name
        :return: File buffer
        '''
        if self.type == "s3":
            bucket = self.folder.get_bucket()
            key = Key(bucket)
            key.key = self.name
            return buffer(key.get_contents_as_string())
        return super(NereidStaticFile, self).get_file_binary(name)

    def get_file_path(self, name):
        """
        Returns path for given static file

        :param static_file: Browse record of the static file
        """
        if self.type == "s3":
            return '/'.join(
                [self.folder.s3_cloudfront_cname, self.name]
            )
        return super(NereidStaticFile, self).get_file_path(name)

    def on_change_type(self):
        """
        Changes the value of functional field when type is changed

        :return: Updated value of functional field
        """
        return {
            'is_s3_bucket': self['type'] == 's3'
        }

    @classmethod
    def get_is_s3_bucket(cls, files, name):
        """
        Gets value of s3_use_bucket of folder

        :param files: Browse record of static file
        :param name: Field name
        :return: value of field
        """
        res = {}
        for file in files:
            res[file.id] = bool(file.folder.s3_use_bucket)
        return res

    def check_use_s3_bucket(self):
        """
        Checks if type is S3 then folder must have use_s3_bucket
        """
        if self.type == "s3" and not self.folder.s3_use_bucket:
            return False
        return True

    @classmethod
    def __setup__(cls):
        super(NereidStaticFile, cls).__setup__()

        cls._constraints += [
            ('check_use_s3_bucket', 's3_bucket_required'),
        ]
        cls._error_messages.update({
            "s3_bucket_required": "Folder must have s3 bucket if type is 'S3'",
        })
