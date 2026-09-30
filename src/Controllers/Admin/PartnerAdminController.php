<?php

namespace Cauri\Controllers\Admin;

use Cauri\Core\HttpException;
use Cauri\Core\Request;
use Cauri\Core\Response;
use Cauri\Repositories\PartnerRepository;
use Cauri\Services\Audit;

/** Partenaires officiels : nom, logo, site, type de partenariat, ordre d'affichage. */
final class PartnerAdminController extends BaseAdminController
{
    public function index(Request $request): Response
    {
        $this->requireUser($request);
        return $this->admin('partners', ['rows' => (new PartnerRepository($this->db))->all()]);
    }

    public function form(Request $request): Response
    {
        $this->requireUser($request);
        $id = $request->param('id');
        $item = $id === 'nouveau'
            ? ['id' => null, 'name' => '', 'url' => '', 'tier' => 'officiel', 'description' => '', 'logo_path' => null, 'sort_order' => 0, 'is_active' => 1]
            : (new PartnerRepository($this->db))->find((int) $id);
        if (!$item) {
            throw new HttpException(404);
        }
        return $this->admin('partner-form', ['item' => $item, 'tiers' => PartnerRepository::TIERS]);
    }

    public function save(Request $request): Response
    {
        $this->requireUser($request);
        $repo = new PartnerRepository($this->db);
        $id = $request->param('id') === 'nouveau' ? null : (int) $request->param('id');
        $back = path('admin/partenaires/' . ($id ?? 'nouveau'));
        $name = mb_substr($request->str('name'), 0, 120);
        $url = $request->str('url');
        $tier = $request->str('tier');
        if ($name === '' || !in_array($tier, PartnerRepository::TIERS, true) || ($url !== '' && !preg_match('#^https?://[^\s<>"]+$#i', $url))) {
            return $this->back($back, 'error', t('admin.partner_invalid'));
        }
        $data = [
            'name'        => $name,
            'url'         => $url ?: null,
            'tier'        => $tier,
            'description' => mb_substr($request->str('description'), 0, 240) ?: null,
            'sort_order'  => (int) $request->str('sort_order'),
            'is_active'   => $request->str('is_active') === '1' ? 1 : 0,
        ];
        $file = $_FILES['logo'] ?? null;
        if ($file && ($file['error'] ?? UPLOAD_ERR_NO_FILE) !== UPLOAD_ERR_NO_FILE) {
            try {
                $data['logo_path'] = PartnerRepository::storeLogo($file);
            } catch (\InvalidArgumentException $e) {
                return $this->back($back, 'error', $e->getMessage());
            }
        }
        $id = $repo->save($id, $data);
        Audit::log($this->uid(), 'partner.save', 'partner', $id, null, ['name' => $name, 'active' => $data['is_active']], $request->ip());
        return $this->back(path('admin/partenaires'), 'success', t('admin.partner_saved'));
    }

    public function delete(Request $request): Response
    {
        $this->requireUser($request, 'admin');
        $id = (int) $request->param('id');
        (new PartnerRepository($this->db))->delete($id);
        Audit::log($this->uid(), 'partner.delete', 'partner', $id, null, [], $request->ip());
        return $this->back(path('admin/partenaires'), 'success', t('admin.partner_deleted'));
    }
}
