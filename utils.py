import numpy as np


class ShapeError(Exception):
    def __init__(self, x):
        self.x = x

    def __str__(self):
        return self.x


def fundamental_matrix(*args, normalize):
    try:
        x1, x2, npts = process_input_pointpairs(args)
        F = eight_point_algorithm(x1, x2, normalize=normalize)
        return F
    except ShapeError as e:
        print('ShapeError, exception message:', e)
        return None


def process_input_pointpairs(args):
    if len(args) == 2:
        x1 = args[0]
        x2 = args[1]
        if not x1.shape == x2.shape:
            raise ShapeError('the two arguments should have same size')

        if not x1.ndim == 2:
            raise ShapeError('Each input has to be a 2D array')

        npts = max(x1.shape)
        d = min(x1.shape)
        if npts < 8:
            raise ShapeError('At least 8 points are needed to compute the fundamental matrix')

        if d == 2:
            if 2 == x1.shape[0]:  # input is a fat matrix
                x1 = np.r_[x1, np.ones((1, npts))]
                x2 = np.r_[x2, np.ones((1, npts))]
            else:  # input is a tall matrix
                x1 = np.r_[x1.T, np.ones((1, npts))]
                x2 = np.r_[x2.T, np.ones((1, npts))]
        elif d == 3:
            if 3 == x1.shape[1]:  # input is a tall matrix
                x1 = x1.T
                x2 = x2.T
        else:
            raise ShapeError('x1 and x2 must be 2xN or Nx2 or 3xN or Nx3')

    elif len(args) == 1:
        if not args[0].ndim == 2:
            raise ShapeError('Each input has to be a 2D array')
        npts = max(args[0].shape)
        d = min(args[0].shape)
        if npts < 8:
            raise ShapeError('At least 8 points are needed to compute the fundamental matrix')
        if d == 4:
            if 4 == args[0].shape[0]:  # input is a fat matrix
                x1 = np.r_[args[0][0:2], np.ones((1, npts))]
                x2 = np.r_[args[0][2:4], np.ones((1, npts))]
            else:  # input is a tall matrix
                x1 = np.r_[args[0][:, 0:2].T, np.ones((1, npts))]
                x2 = np.r_[args[0][:, 2:4].T, np.ones((1, npts))]
        elif d == 6:
            if 6 == args[0].shape[0]:  # input is a tall matrix
                x1 = args[0][0:3]
                x2 = args[0][3:6]
            else:
                x1 = args[0][:, 0:3].T
                x2 = args[0][:, 3:6].T
        else:
            raise ShapeError('Single argument x must be 4xN or Nx4 or 6xN or Nx6')
    else:
        raise ShapeError('Wrong number of arguments supplied')

    return x1, x2, npts


def eight_point_algorithm(x1, x2, normalize):
    if normalize:
        # perform the normalization (translation and scaling)
        x1, T1 = normalize2dpts(x1)
        x2, T2 = normalize2dpts(x2)

    # assemble the constraint matrix
    A = constraint_matrix(x1, x2)

    # A*vec(F) = 0 implies that the fundamental matrix F can be extracted from
    # singular vector of V corresponding to smallest singular value
    (U, S, V) = np.linalg.svd(A)
    V = V.conj().T
    F = V[:, 8].reshape(3, 3).copy()

    # recall that F should be of rank 2, do the lower-rank approximation by svd
    (U, D, V) = np.linalg.svd(F)
    F = np.dot(np.dot(U, np.diag([D[0], D[1], 0])), V)

    if normalize:
        # denormalize
        F = np.dot(np.dot(T2.T, F), T1)
    return F


def constraint_matrix(x1, x2):
    npts = x1.shape[1]
    # stack column by column
    A = np.c_[
        x2[0] * x1[0], x2[0] * x1[1], x2[0], x2[1] * x1[0], x2[1] * x1[1], x2[1], x1[0], x1[1], np.ones((npts, 1))]
    return A


def normalize2dpts(pts):
    ''' This function translates and scales the input (homogeneous) points
    such that the output points are centered at origin and the mean distance
    from the origin is sqrt(2). As shown in Hartley (1997), this normalization
    process typically improves the condition number of the linear systems used
    for solving homographies, fundamental matrices, etc.

    References:
        Richard Hartley, PAMI 1997
        Peter Kovesi, MATLAB functions for computer vision and image processing,
        http://www.csse.uwa.edu.au/~pk
     '''
    if pts.shape[0] != 3:
        raise ShapeError('pts must be 3xN')

    finiteind = abs(pts[2]) > np.finfo(float).eps
    pts[0, finiteind] = pts[0, finiteind] / pts[2, finiteind]
    pts[1, finiteind] = pts[1, finiteind] / pts[2, finiteind]
    pts[2, finiteind] = 1

    # Centroid of finite points
    c = [np.mean(pts[0, finiteind]), np.mean(pts[1, finiteind])]

    # Shift origin to centroid.
    newp0 = pts[0, finiteind] - c[0]
    newp1 = pts[1, finiteind] - c[1]

    meandist = np.mean(np.sqrt(newp0 ** 2 + newp1 ** 2))

    scale = np.sqrt(2) / meandist
    '''
    T = [scale   0   -scale*c(1)
         0     scale -scale*c(2)
         0       0      1      ];
    '''
    T = np.eye(3)
    T[0][0] = scale
    T[1][1] = scale
    T[0][2] = -scale * c[0]
    T[1][2] = -scale * c[1]
    newpts = np.dot(T, pts)

    return newpts, T


def calc_errors(disparity_matrix, gt):
    flat_d = disparity_matrix.flatten()
    flat_gt = gt[:, :, 0].flatten()/3
    errors = np.asarray([abs(e1 - e2) for e1, e2 in zip(flat_gt, flat_d)])
    avg_error = np.mean(errors)
    med_error = np.median(errors)
    bad_05 = ((np.where(errors > 0.5)[0].shape[0]) / errors.shape[0]) * 100
    bad_4 = ((np.where(errors > 4)[0].shape[0]) / errors.shape[0]) * 100

    return avg_error, med_error, bad_05, bad_4
