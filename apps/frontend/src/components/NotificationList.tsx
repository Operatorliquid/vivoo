import { Icon } from '@courtvision/design-system';
import type { OwnerNotification } from '../lib/api';

const KIND_ICON: Record<OwnerNotification['kind'], string> = {
  camera: 'camera',
  highlight: 'clip',
  session: 'qr',
};

/**
 * Actividad del club. La severidad se marca con la línea izquierda y con el
 * icono, nunca solo con color.
 */
export function NotificationList({
  notifications,
  onRead,
  dense = false,
}: { notifications: OwnerNotification[]; onRead: (id: string) => void; dense?: boolean }) {
  return (
    <ul className={`activity-list ${dense ? 'activity-list--dense' : ''}`}>
      {notifications.map((notification) => (
        <li key={notification.id} className={`activity-row activity-row--${notification.severity} ${notification.read ? 'is-read' : ''}`}>
          <span className="activity-row__mark" aria-hidden="true">
            <Icon name={KIND_ICON[notification.kind]} size={14} />
          </span>
          <div className="activity-row__body">
            <b>
              {!notification.read ? <i className="activity-row__unread" aria-label="Sin leer" /> : null}
              {notification.title}
            </b>
            {notification.detail ? <p>{notification.detail}</p> : null}
            <span className="t-meta">{notification.time}</span>
          </div>
          {!notification.read ? (
            <button type="button" className="activity-row__read" onClick={() => onRead(notification.id)}>
              Marcar leída
            </button>
          ) : null}
        </li>
      ))}
    </ul>
  );
}
