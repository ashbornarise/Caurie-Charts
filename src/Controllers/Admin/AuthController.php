<?php

namespace Cauri\Controllers\Admin;

use Cauri\Core\Csrf;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Core\Session;
use Cauri\Core\View;
use Cauri\Services\Security\Auth;

final class AuthController extends BaseAdminController
{
    public function loginForm(Request $request): Response
    {
        if ((new Auth($this->db))->user()) {
            return Response::redirect(path('admin'));
        }
        return $this->guest('login', []);
    }

    public function login(Request $request): Response
    {
        Csrf::check($request);
        $result = (new Auth($this->db))->attempt($request->str('email'), (string) ($request->post['password'] ?? ''), $request->ip());
        return match ($result) {
            'ok'     => Response::redirect(path('admin')),
            '2fa'    => Response::redirect(path('admin/2fa')),
            'locked' => $this->guest('login', ['error' => t('admin.login_locked')], 429),
            default  => $this->guest('login', ['error' => t('admin.login_invalid'), 'email' => $request->str('email')], 401),
        };
    }

    public function twoFactorForm(Request $request): Response
    {
        if (!Session::get('2fa_user')) {
            return Response::redirect(path('admin/connexion'));
        }
        return $this->guest('two-factor', []);
    }

    public function twoFactor(Request $request): Response
    {
        Csrf::check($request);
        $result = (new Auth($this->db))->verifySecondFactor($request->str('code'), $request->ip());
        return match ($result) {
            'ok'      => Response::redirect(path('admin')),
            'expired' => $this->guest('login', ['error' => t('admin.2fa_expired')], 401),
            'locked'  => $this->guest('login', ['error' => t('admin.login_locked')], 429),
            default   => $this->guest('two-factor', ['error' => t('admin.2fa_invalid')], 401),
        };
    }

    public function logout(Request $request): Response
    {
        Csrf::check($request);
        (new Auth($this->db))->logout();
        return Response::redirect(path('admin/connexion'));
    }

    private function guest(string $template, array $data, int $status = 200): Response
    {
        $response = View::page('admin/' . $template, $data + ['user' => null, 'flash' => [], 'title' => t('admin.login')], $status, 'admin/layout');
        $response->headers['Cache-Control'] = 'no-store';
        return $response;
    }
}
