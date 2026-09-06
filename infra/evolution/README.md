# Evolution API local service

Evolution API is part of the CourtVision deployment. PostgreSQL stores the Evolution instance data, Redis handles its cache/queue, and the instance volume preserves the WhatsApp connection between restarts.

Start it with:

```bash
./infra/evolution/start.sh
```

The script generates `infra/evolution/.env` on first run. That file is ignored by Git and contains the Evolution API key plus the database password. The API is bound to localhost during local development; in AWS it should sit on the private application network behind the CourtVision API/worker.

Owners do not receive this API key. In vivoo they open **Configuración →
WhatsApp**, request their QR and scan it from **Dispositivos vinculados**. vivoo
derives one stable opaque instance per owner, while the media worker selects that
instance when sending each player's highlight.
