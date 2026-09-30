<?php

namespace Cauri\Controllers\Admin;

use Cauri\Controllers\Controller;
use Cauri\Core\Csrf;
use Cauri\Core\HttpException;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Core\Session;
use Cauri\Core\View;
use Cauri\Services\Security\Auth;

/** Toutes les pages d'admin exigent une connexion ; certaines actions exigent le rôle admin. */
abstract class BaseAdminController extends Controller
{
    protected ?array $user = null;

    protected function requireUser(Request $request, string $role = 'editor'): void
    {
        $this->user = (new Auth($this->db))->user();
        if (!$this->user) {
            throw new RedirectException(path('admin/connexion'));
        }
        if ($role === 'admin' && $this->user['role'] !== 'admin') {
            throw new HttpException(403);
        }
        if ($request->method === 'POST') {
            Csrf::check($request);
        }
    }

    protected function admin(string $template, array $data = []): Response
    {
        $response = View::page('admin/' . $template, $data + [
            'user'  => $this->user,
            'flash' => Session::takeFlash(),
            'title' => t('admin.title'),
        ], 200, 'admin/layout');
        $response->headers['Cache-Control'] = 'no-store';
        $response->headers['X-Robots-Tag'] = 'noindex, nofollow';
        return $response;
    }

    protected function back(string $to, string $type = 'success', ?string $message = null): Response
    {
        if ($message !== null) {
            Session::flash($type, $message);
        }
        return Response::redirect($to);
    }

    protected function uid(): int
    {
        return (int) $this->user['id'];
    }
}
