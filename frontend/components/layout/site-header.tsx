import { LogoutButton } from "../../features/auth/logout-button";
import Link from "next/link";

export function SiteHeader({
  authenticated,
  canAccessAdminPanel,
}: {
  authenticated: boolean;
  canAccessAdminPanel: boolean;
}) {
  return (
    <header className="site-header">
      <div className="shell header-inner">
        <Link className="wordmark" href="/#inicio" aria-label="Cianci — inicio">
          <span className="wordmark-name">
            Cianci<span aria-hidden="true">.</span>
          </span>
          <span className="wordmark-caption">Instituto de Danzas</span>
        </Link>
        <nav aria-label="Navegación principal" className="site-nav">
          <Link href="/#instituto">El instituto</Link>
          <Link href="/espectaculos">Espectáculos</Link>
          <Link href="/#disciplinas">
            Disciplinas <span aria-hidden="true">↗</span>
          </Link>
          {authenticated ? (
            <>
              <Link href="/mi-cuenta">Mi cuenta</Link>
              <Link href="/mi-calendario">Mi calendario</Link>
              {canAccessAdminPanel ? (
                <Link href="/admin-panel">Panel administrativo</Link>
              ) : null}
              <LogoutButton />
            </>
          ) : (
            <Link href="/ingresar">Ingresar</Link>
          )}
        </nav>
      </div>
    </header>
  );
}
