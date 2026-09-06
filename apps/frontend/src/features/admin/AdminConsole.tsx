import { useEffect, useMemo, useState } from 'react';
import { Avatar, Banner, Button, EmptyState, Icon, Skeleton, ThemeToggle, useTheme } from '@courtvision/design-system';
import { Brand, BrandMark } from '../../components/Brand';
import { getAdminOverview } from '../../lib/api';
import type { AdminCustomer, AdminOverview, OwnerSession } from '../../lib/api';
import { CreateCustomerDialog } from './CreateCustomerDialog';

type AdminSection = 'operation' | 'customers' | 'customer';

function routeFromPath(): { section: AdminSection; customerId: string | null } {
  const match = window.location.pathname.match(/^\/admin\/customers\/([^/]+)/);
  if (match) return { section: 'customer', customerId: decodeURIComponent(match[1]) };
  if (window.location.pathname.startsWith('/admin/customers')) return { section: 'customers', customerId: null };
  return { section: 'operation', customerId: null };
}

function navigate(path: string) {
  window.history.pushState({}, '', path);
  window.dispatchEvent(new PopStateEvent('popstate'));
}

const statusText = { operational: 'Operativo', attention: 'Requiere atención', setup: 'Sin configurar' } as const;

function initials(value: string) {
  return value.split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0]).join('').toUpperCase() || 'TV';
}

function relativeTime(value: string | null) {
  if (!value) return 'Sin conexión registrada';
  const seconds = Math.max(0, Math.round((Date.now() - new Date(value).getTime()) / 1000));
  if (seconds < 60) return 'Ahora';
  if (seconds < 3600) return `Hace ${Math.floor(seconds / 60)} min`;
  if (seconds < 86400) return `Hace ${Math.floor(seconds / 3600)} h`;
  return new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: 'short' }).format(new Date(value));
}

function Status({ value }: { value: AdminCustomer['status'] }) {
  return <span className={`admin-status admin-status--${value}`}><i />{statusText[value]}</span>;
}

function CustomerRow({ customer }: { customer: AdminCustomer }) {
  const club = customer.club?.name || 'Club sin configurar';
  return (
    <li className="admin-customer-row">
      <button type="button" onClick={() => navigate(`/admin/customers/${encodeURIComponent(customer.id)}`)}>
        <span className="admin-customer-row__identity">
          {customer.club?.logo_data_url
            ? <img src={customer.club.logo_data_url} alt="" />
            : <Avatar initials={initials(club)} size="sm" />}
          <span><b>{club}</b><small>{customer.display_name} · {customer.email}</small></span>
        </span>
        <Status value={customer.status} />
        <span className="admin-customer-row__metric"><b>{customer.metrics.courts}</b><small>Canchas</small></span>
        <span className="admin-customer-row__metric"><b>{customer.metrics.cameras_online}/{customer.metrics.cameras}</b><small>Cámaras online</small></span>
        <span className="admin-customer-row__metric"><b>{customer.metrics.active_recordings}</b><small>Grabando</small></span>
        <span className="admin-customer-row__seen">{relativeTime(customer.last_seen_at)}</span>
        <Icon name="chevronRight" size={16} />
      </button>
    </li>
  );
}

function Summary({ data }: { data: AdminOverview }) {
  const items = [
    { label: 'Clientes', value: data.summary.customers, icon: 'user' },
    { label: 'Canchas', value: data.summary.courts, icon: 'court' },
    { label: 'Cámaras online', value: `${data.summary.cameras_online}/${data.summary.cameras}`, icon: 'camera' },
    { label: 'Grabaciones activas', value: data.summary.active_recordings, icon: 'record' },
  ];
  return (
    <section className="admin-summary" aria-label="Estado general">
      {items.map((item) => (
        <article key={item.label}>
          <span><Icon name={item.icon} size={17} /></span>
          <div><strong className="t-figure">{item.value}</strong><small>{item.label}</small></div>
        </article>
      ))}
    </section>
  );
}

function CustomerList({ customers, emptyText }: { customers: AdminCustomer[]; emptyText: string }) {
  if (!customers.length) return <EmptyState compact icon="search" title={emptyText}>No hay resultados para mostrar.</EmptyState>;
  return <ul className="admin-customer-list row-list">{customers.map((item) => <CustomerRow customer={item} key={item.id} />)}</ul>;
}

function OperationPage({ data }: { data: AdminOverview }) {
  const attention = data.customers.filter((item) => item.status === 'attention');
  const current = data.customers.slice(0, 5);
  return (
    <div className="page page-enter admin-page">
      <Summary data={data} />
      {attention.length > 0 ? (
        <section className="admin-block admin-block--attention">
          <header><div><span className="t-label">Atención</span><h2 className="t-heading">Intervención necesaria</h2></div><b>{attention.length}</b></header>
          <CustomerList customers={attention} emptyText="Sin incidencias" />
        </section>
      ) : (
        <section className="admin-all-clear">
          <span><Icon name="check" size={18} /></span>
          <div><b>Operación estable</b><small>No hay incidencias activas en los clubes configurados.</small></div>
        </section>
      )}
      <section className="admin-block">
        <header>
          <div><span className="t-label">Clientes</span><h2 className="t-heading">Estado reciente</h2></div>
          <Button variant="ghost" size="sm" iconAfter="arrowRight" onClick={() => navigate('/admin/customers')}>Ver todos</Button>
        </header>
        <CustomerList customers={current} emptyText="Todavía no hay clientes" />
      </section>
    </div>
  );
}

function CustomersPage({ data, token, onCreated }: { data: AdminOverview; token: string; onCreated: () => void }) {
  const [query, setQuery] = useState('');
  const [creating, setCreating] = useState(false);
  const filtered = useMemo(() => {
    const needle = query.trim().toLocaleLowerCase('es');
    if (!needle) return data.customers;
    return data.customers.filter((item) => `${item.display_name} ${item.email} ${item.club?.name ?? ''} ${item.club?.city ?? ''}`.toLocaleLowerCase('es').includes(needle));
  }, [data.customers, query]);
  return (
    <div className="page page-enter admin-page">
      <div className="admin-directory-head">
        <div><span className="t-label">Directorio</span><p>{data.customers.length} {data.customers.length === 1 ? 'cliente' : 'clientes'}</p></div>
        <div className="admin-directory-head__actions">
          <label className="admin-search"><Icon name="search" size={16} /><span className="u-visually-hidden">Buscar clientes</span><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar por club, titular o email" /></label>
          <Button variant="primary" iconBefore="plus" onClick={() => setCreating(true)}>Crear usuario</Button>
        </div>
      </div>
      <section className="admin-block admin-block--directory">
        <CustomerList customers={filtered} emptyText="No encontramos ese cliente" />
      </section>
      <CreateCustomerDialog open={creating} token={token} onClose={() => setCreating(false)} onCreated={onCreated} />
    </div>
  );
}

function CustomerPage({ customer }: { customer: AdminCustomer }) {
  const club = customer.club?.name || 'Club sin configurar';
  return (
    <div className="page page-enter admin-page">
      <section className="admin-customer-head">
        <div className="admin-customer-head__identity">
          {customer.club?.logo_data_url ? <img src={customer.club.logo_data_url} alt="" /> : <Avatar initials={initials(club)} />}
          <div><h2 className="t-display">{club}</h2><p>{customer.display_name} · {customer.email}</p></div>
        </div>
        <Status value={customer.status} />
      </section>
      <section className="admin-detail-metrics">
        <article><small>Canchas</small><b className="t-figure">{customer.metrics.courts}</b></article>
        <article><small>Cámaras online</small><b className="t-figure">{customer.metrics.cameras_online}<em>/{customer.metrics.cameras}</em></b></article>
        <article><small>Grabando ahora</small><b className="t-figure">{customer.metrics.active_recordings}</b></article>
        <article><small>Highlights</small><b className="t-figure">{customer.metrics.highlights}</b></article>
      </section>
      <section className="admin-block">
        <header><div><span className="t-label">Infraestructura</span><h2 className="t-heading">Canchas y cámaras</h2></div><small>Última señal: {relativeTime(customer.last_seen_at)}</small></header>
        {customer.courts.length ? (
          <ul className="admin-courts">
            {customer.courts.map((court) => (
              <li key={court.id}>
                <span className="admin-courts__icon"><Icon name="court" size={18} /></span>
                <span className="admin-courts__name"><b>{court.name}</b><small>{court.sport_code === 'football' ? 'Fútbol' : 'Pádel'} · {court.status === 'maintenance' ? 'Mantenimiento' : court.status === 'inactive' ? 'Inactiva' : 'Activa'}</small></span>
                <span className={`admin-camera-state ${court.camera?.status === 'online' ? 'is-online' : 'is-offline'}`}><i />{court.camera ? (court.camera.status === 'online' ? 'Cámara online' : 'Cámara offline') : 'Sin cámara'}</span>
                <span className={`admin-recording-state ${court.recording ? 'is-live' : ''}`}><Icon name={court.recording ? 'record' : 'stop'} size={12} />{court.recording ? 'Grabando' : 'En espera'}</span>
                <small className="admin-courts__seen">{relativeTime(court.camera?.last_seen_at ?? null)}</small>
              </li>
            ))}
          </ul>
        ) : <EmptyState compact icon="court" title="Sin canchas configuradas">Este cliente todavía no configuró su infraestructura.</EmptyState>}
      </section>
      {(customer.metrics.highlights_pending > 0 || customer.metrics.highlights_failed > 0) ? (
        <Banner tone={customer.metrics.highlights_failed > 0 ? 'error' : 'warning'} title="Procesamiento de highlights">
          {customer.metrics.highlights_pending} pendientes · {customer.metrics.highlights_failed} fallidos
        </Banner>
      ) : null}
    </div>
  );
}

export function AdminConsole({ session, onLogout }: { session: OwnerSession; onLogout: () => void }) {
  const [route, setRoute] = useState(routeFromPath);
  const [data, setData] = useState<AdminOverview | null>(null);
  const [error, setError] = useState('');
  const [refreshing, setRefreshing] = useState(false);
  const { theme, toggleTheme } = useTheme();

  const load = async () => {
    setRefreshing(true);
    try { setData(await getAdminOverview(session.access_token)); setError(''); }
    catch (reason) { setError(reason instanceof Error ? reason.message : 'No pudimos leer la operación.'); }
    finally { setRefreshing(false); }
  };

  useEffect(() => { void load(); }, [session.access_token]);
  useEffect(() => {
    const update = () => setRoute(routeFromPath());
    window.addEventListener('popstate', update);
    return () => window.removeEventListener('popstate', update);
  }, []);

  const customer = route.customerId ? data?.customers.find((item) => item.id === route.customerId) ?? null : null;
  const title = route.section === 'operation' ? 'Operación' : route.section === 'customers' ? 'Clientes' : 'Cliente';

  return (
    <div className="console admin-console">
      <a className="skip-link" href="#contenido">Saltar al contenido</a>
      <aside className="rail admin-rail">
        <div className="rail__brand"><Brand /></div>
        <div className="admin-rail__scope"><BrandMark size={13} /><span>Control central</span></div>
        <nav className="rail-nav" aria-label="Administración">
          <button type="button" className={`rail-nav__item ${route.section === 'operation' ? 'is-active' : ''}`} onClick={() => navigate('/admin')}><Icon name="board" size={18} /><span>Operación</span></button>
          <button type="button" className={`rail-nav__item ${route.section !== 'operation' ? 'is-active' : ''}`} onClick={() => navigate('/admin/customers')}><Icon name="user" size={18} /><span>Clientes</span>{data?.summary.customers ? <em className="rail-nav__badge">{data.summary.customers}</em> : null}</button>
        </nav>
        <div className="rail__foot">
          <div className="rail__account"><Avatar initials={initials(session.user.display_name)} size="sm" /><span className="rail__user"><b>{session.user.display_name}</b><small>{session.user.email}</small></span></div>
          <button type="button" className="rail__logout" onClick={onLogout}><Icon name="logout" size={16} /> Cerrar sesión</button>
        </div>
      </aside>
      <div className="console__main">
        <header className="topbar admin-topbar">
          <div className="topbar__mobile-brand"><Brand compact /></div>
          {route.section === 'customer' ? <button type="button" className="topbar__back" onClick={() => navigate('/admin/customers')} aria-label="Volver a clientes"><Icon name="arrowLeft" size={16} /></button> : null}
          <div className="topbar__title"><h1 className="t-title">{title}</h1><p className="topbar__context">Administración vivoo</p></div>
          <div className="topbar__actions">
            <ThemeToggle theme={theme} onToggle={toggleTheme} />
            <button type="button" className="topbar__sync" onClick={() => void load()} disabled={refreshing}><Icon name="refresh" size={15} className={refreshing ? 'is-spinning' : ''} /><span>Actualizar</span></button>
          </div>
        </header>
        <main className="canvas" id="contenido" tabIndex={-1}>
          {error ? <Banner tone="error" title="No pudimos sincronizar" action={<Button variant="secondary" size="sm" onClick={() => void load()}>Reintentar</Button>}>{error}</Banner> : null}
          {!data && !error ? <div className="admin-loading"><Skeleton h={124} /><Skeleton h={260} /></div> : null}
          {data && route.section === 'operation' ? <OperationPage data={data} /> : null}
          {data && route.section === 'customers' ? <CustomersPage data={data} token={session.access_token} onCreated={() => void load()} /> : null}
          {data && route.section === 'customer' && customer ? <CustomerPage customer={customer} /> : null}
          {data && route.section === 'customer' && !customer ? <EmptyState icon="search" title="Cliente no encontrado" action={<Button variant="secondary" size="sm" onClick={() => navigate('/admin/customers')}>Volver a clientes</Button>} /> : null}
        </main>
        <nav className="tab-nav admin-tab-nav" aria-label="Administración">
          <button type="button" className={`tab-nav__item ${route.section === 'operation' ? 'is-active' : ''}`} onClick={() => navigate('/admin')}><Icon name="board" size={20} /><span>Operación</span></button>
          <button type="button" className={`tab-nav__item ${route.section !== 'operation' ? 'is-active' : ''}`} onClick={() => navigate('/admin/customers')}><Icon name="user" size={20} /><span>Clientes</span></button>
        </nav>
      </div>
    </div>
  );
}
