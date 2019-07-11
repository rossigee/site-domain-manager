import databases
import orm
import sqlalchemy

from sdmgr import settings

database = databases.Database(settings.DATABASE_URL)
metadata = sqlalchemy.MetaData()


class Hosting(orm.Model):
    __tablename__ = "hosting"
    __database__ = database
    __metadata__ = metadata

    id = orm.Integer(primary_key=True)
    label = orm.String(max_length=100)
    agent_module = orm.String(max_length=100)
    config_id = orm.String(max_length=100, allow_null=True)
    state = orm.Text(default="{}")
    active = orm.Boolean(default=True)

    async def serialize(self):
        await self.load()
        return {
            "id": self.id,
            "label": self.label
        }


class Site(orm.Model):
    __tablename__ = "sites"
    __database__ = database
    __metadata__ = metadata

    id = orm.Integer(primary_key=True)
    label = orm.String(max_length=100)
    hosting = orm.ForeignKey(Hosting)
    active = orm.Boolean(default=True)

    async def serialize(self):
        await self.load()
        return {
            "id": self.id,
            "label": self.label
        }


class Registrar(orm.Model):
    __tablename__ = "registrars"
    __database__ = database
    __metadata__ = metadata

    id = orm.Integer(primary_key=True)
    label = orm.String(max_length=100)
    agent_module = orm.String(max_length=100)
    config_id = orm.String(max_length=100, allow_null=True)
    state = orm.Text(default="{}")
    active = orm.Boolean(default=True)

    async def serialize(self):
        await self.load()
        return {
            "id": self.id,
            "label": self.label
        }


class DNSProvider(orm.Model):
    __tablename__ = "dns_providers"
    __database__ = database
    __metadata__ = metadata

    id = orm.Integer(primary_key=True)
    label = orm.String(max_length=100)
    agent_module = orm.String(max_length=100)
    config_id = orm.String(max_length=100, allow_null=True)
    state = orm.Text(default="{}")
    active = orm.Boolean(default=True)

    async def serialize(self, full = False):
        await self.load()
        r = {
            "id": self.id,
            "label": self.label
        }
        if full:
            r['agent_module'] = self.agent_module
            r['active'] = self.active
        return r


class WAFProvider(orm.Model):
    __tablename__ = "waf_providers"
    __database__ = database
    __metadata__ = metadata

    id = orm.Integer(primary_key=True)
    label = orm.String(max_length=100)
    agent_module = orm.String(max_length=100)
    config_id = orm.String(max_length=100, allow_null=True)
    state = orm.Text(default="{}")
    active = orm.Boolean(default=True)

    async def serialize(self):
        await self.load()
        return {
            "id": self.id,
            "label": self.label
        }


class Domain(orm.Model):
    __tablename__ = "domains"
    __database__ = database
    __metadata__ = metadata

    id = orm.Integer(primary_key=True)
    name = orm.String(max_length=100)
    registrar = orm.ForeignKey(Registrar)
    dns = orm.ForeignKey(DNSProvider, allow_null=True)
    site = orm.ForeignKey(Site, allow_null=True)
    waf = orm.ForeignKey(WAFProvider, allow_null=True)
    update_apex = orm.Boolean(default=True)
    update_a_records = orm.Text(default="www")
    google_site_verification = orm.String(max_length=64, allow_null=True)
    state = orm.Text(default="{}")
    active = orm.Boolean(default=True)

    async def serialize(self):
        #await self.load()
        r = {
            "id": self.id,
            "name": self.name,
        }
        if self.registrar.id:
            r["registrar"] = await self.registrar.serialize()
        if self.dns.id:
            r["dns"] = await self.dns.serialize()
        if self.site.id:
            r["site"] = await self.site.serialize()
        if self.waf.id:
            r["waf"] = await self.waf.serialize()
        if self.active:
            r["active"] = True
        return r


# Create the database
engine = sqlalchemy.create_engine(str(database.url))
metadata.create_all(engine)