from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from app.models.provinceAndDistrict import Province, District

bp = Blueprint('province', __name__)

@bp.route('', methods=['GET'])
def get_provinces():
    """Get all provinces"""
    try:
        from sqlalchemy.orm import joinedload
        provinces = Province.query.options(joinedload(Province.districts)).all()

        provinces_with_districts = []

        for province in provinces:
            province_data = province.to_dict()
            province_data['districts'] = [district.to_dict() for district in province.districts]
            provinces_with_districts.append(province_data)

        return jsonify({
            'provinces': provinces_with_districts
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get provinces: {str(e)}'}), 500

@bp.route('/<int:province_id>/districts', methods=['GET'])
def get_districts_by_province(province_id):
    """Get all districts in a province"""
    try:
        province = Province.query.get_or_404(province_id)
        districts = District.query.filter_by(province_id=province_id).all()
        return jsonify({
            'province': province.to_dict(),
            'districts': [district.to_dict() for district in districts]
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get districts: {str(e)}'}), 500

@bp.route('/districts', methods=['GET'])
def get_all_districts():
    """Get all districts"""
    try:
        districts = District.query.all()
        return jsonify({
            'districts': [district.to_dict() for district in districts]
        })
    except Exception as e:
        return jsonify({'error': f'Failed to get districts: {str(e)}'}), 500