import { useState } from 'react';
import { Button, Dialog, EmptyState } from '@courtvision/design-system';
import { NotificationList } from '../../components/NotificationList';
import type { OwnerConsole } from '../../app/useOwnerConsole';

export function NotificationCenterPage({ console: data }: { console: OwnerConsole }) {
  const [clearOpen, setClearOpen] = useState(false);
  const unread = data.notifications.filter((item) => !item.read).length;

  return (
    <div className="page page-enter notifications-page">
      <header className="notifications-page__bar">
        <div>
          <h2 className="t-heading">Notificaciones</h2>
          <span className="t-meta">{data.notifications.length > 0 ? `${data.notifications.length} avisos · ${unread} sin leer` : 'Todo al día'}</span>
        </div>
        {data.notifications.length > 0 ? (
          <div className="card__tools">
            {unread > 0 ? <Button size="sm" variant="ghost" onClick={() => void data.actions.readAllNotifications()}>Marcar todo leído</Button> : null}
            <Button size="sm" variant="danger" iconBefore="trash" onClick={() => setClearOpen(true)}>Eliminar todas</Button>
          </div>
        ) : null}
      </header>

      {data.notifications.length > 0 ? (
        <section className="notifications-page__list" aria-label="Notificaciones del club">
          <NotificationList notifications={data.notifications} onRead={(id) => void data.actions.readNotification(id)} />
        </section>
      ) : (
        <section className="notifications-page__empty">
          <EmptyState icon="bell" accent="ice" title="No hay notificaciones pendientes" />
        </section>
      )}

      <Dialog
        open={clearOpen}
        onClose={() => setClearOpen(false)}
        size="sm"
        tone="danger"
        title="Eliminar todas las notificaciones"
        description="Esta acción no se puede deshacer."
        footer={
          <>
            <Button variant="ghost" onClick={() => setClearOpen(false)}>Cancelar</Button>
            <Button variant="danger" onClick={async () => { await data.actions.clearNotifications(); setClearOpen(false); }}>Eliminar todas</Button>
          </>
        }
      >
        <p className="dialog-copy">Se borran los {data.notifications.length} avisos registrados en este club.</p>
      </Dialog>
    </div>
  );
}
